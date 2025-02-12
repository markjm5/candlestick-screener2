import os, sys, time #csv
import multiprocessing
import concurrent.futures
from datetime import datetime, date, timedelta
import glob
import json
import yfinance as yf
import pandas as pd
from flask import Flask, escape, request, render_template
from patterns import candlestick_patterns
from chartlib import get_ticker_data, get_breakout_data, load_data_from_pickle
from chartlib import scrape_table_earningswhispers_earnings_calendar, scrape_table_marketscreener_economic_calendar
from chartlib import scrape_table_insider_trades, exchanges

# TODO: Ticker Geographic Exposure Search
# TODO: ATR Monthly, ATR Quarterly, Price Action csv download
# TODO: Add Common Header
# TODO: Add Header Menu Links

app = Flask(__name__)

todays_date = date.today()
date_str_today = "%s-%s-%s" % (todays_date.year, todays_date.month, todays_date.day)
date_str_start = "2007-01-01"

list_of_files = glob.glob('datasets/*.csv',) # * means all if need specific format then *.csv
latest_file = max(list_of_files, key=os.path.getctime)
latest_file = latest_file.replace("datasets\\", "")

@app.route('/snapshot')
def snapshot():
    
    now_start = datetime.now()
    start_time = now_start.strftime("%H:%M:%S")    

    data_tickers =  {'ticker': [],'company': [], 'sector': [], 'industry': [], 'shares_outstanding': [], 'market_cap': [], 'exchange': [],'last_volume': [], 'vs_avg_vol_10d': [], 'vs_avg_vol_3m': [], 'outlook': [],  'percentage': [], 'last': []}    
    df_tickers_partial = pd.DataFrame(data_tickers)

    header = True
    with open('datasets/{}'.format(latest_file)) as f:
        for line in f:
            if "," not in line:
                continue

            if(header):
                header = False
                continue
            else:
                symbol = line.split(",")[1]
                symbol = symbol.replace("\"","")
                company = line.split(",")[0].replace('\"','')
                sector = line.split(",")[7].replace('\"','')
                industry = line.split(",")[8].replace('\"','')
                exchange = line.split(",")[5].replace('\"','')

                #TODO: Get market cap as well, because we want to use it in the earnings calendar
                market_cap = line.split(",")[2].replace('\"','')
                exchanges = ['NYSE', 'NSDQ']
                #TODO: Check that Company is not empty, and only add to the master ticker file if company is not empty
                if(company != '' and exchange in exchanges):
                    try:
                        shares_outstanding = float(line.split(",")[41].replace('\n', '').replace('\"',''))
                        shares_outstanding = shares_outstanding *1000000                    
                    except Exception as e:
                        shares_outstanding = 0

                    data = yf.download(symbol, start=date_str_start, end=date_str_today)
                    data.to_csv('datasets/daily/{}.csv'.format(symbol))
                    print(symbol)

                    df_tickers_partial.loc[len(df_tickers_partial.index)] = [symbol, company, sector, industry, shares_outstanding,market_cap, exchange,0,0,0,0,0,0]

    df_tickers = get_ticker_data(df_tickers_partial)

    with concurrent.futures.ProcessPoolExecutor() as executor:
        f1 = executor.submit(get_breakout_data, df_tickers)
        f2 = executor.submit(scrape_table_earningswhispers_earnings_calendar, df_tickers)
        f3 = executor.submit(scrape_table_marketscreener_economic_calendar)

    #TODO: This needs to be in a concurrent process. Also get stock data and run in process
    #success = scrape_table_insider_trades(df_tickers)

    now_finish = datetime.now()
    finish_time = now_finish.strftime("%H:%M:%S")

    difference = now_finish - now_start

    seconds_in_day = 24 * 60 * 60

    response = {
        "01_start_time": start_time,
        "02_end_time": finish_time,
        "03_total": divmod(difference.days * seconds_in_day + difference.seconds, 60)
    }

    return render_template("index.html", candlestick_patterns=candlestick_patterns, response=response)


@app.route('/')
def index():
    template = "index.html"
    pattern  = request.args.get('pattern', False)
    stocks = {}
    sectors = {}
    industries = {}
    percentage_dict = {}

    if pattern:
        df_tickers = load_data_from_pickle("01_tickers")

        if(pattern == 'VOLUME'):
            template = "volume.html"

            df_stock_volume = df_tickers.sort_values(by=['vs_avg_vol_3m'], ascending=False)        
            #df_stock_volume = df_stock_volume[df_stock_volume.company != '']
            df_stock_volume = df_stock_volume[df_stock_volume.vs_avg_vol_3m > 0]

            for index, row in df_stock_volume.iterrows():
                stocks[row['ticker']] = {'company': row['company'], 'vs_avg_vol_10d': "{:.2%}".format(row['vs_avg_vol_10d']),'vs_avg_vol_3m': "{:.2%}".format(row['vs_avg_vol_3m']), 'pattern': row['outlook'], 'sector': row['sector'], 'industry': row['industry'], 'last':"{:.2f}".format(row['last'])}

            df_percentage = df_stock_volume.sort_values(by=['percentage'], ascending=False).reset_index() 
            df_percentage = df_percentage.drop(['vs_avg_vol_10d','vs_avg_vol_3m'], axis=1)
            df_percentage = df_percentage[df_percentage.percentage > 0.05]

            for index, row in df_percentage.iterrows():
                percentage_dict[row['ticker']] = {'company': row['company'],'pattern': row['outlook'], 'sector': row['sector'], 'industry': row['industry'], 'percentage':  "{:.2%}".format(row['percentage']),'last':"{:.2f}".format(row['last'])}

            df_vol_data_all_sectors = df_stock_volume.drop(['company','ticker','industry','vs_avg_vol_10d','vs_avg_vol_3m', 'outlook'], axis=1)

            df_vol_data_all_sectors = df_vol_data_all_sectors.groupby(['sector']).sum().sort_values(by=['last_volume'], ascending=False).reset_index()

            df_vol_data_all_sectors = df_vol_data_all_sectors.head(5)

            for index, row in df_vol_data_all_sectors.iterrows():
                sectors[row['sector']] = {'volume': row['last_volume']}

            df_vol_data_all_industries = df_stock_volume.drop(['company','ticker','sector','vs_avg_vol_10d','vs_avg_vol_3m', 'outlook'], axis=1)
            df_vol_data_all_industries = df_vol_data_all_industries.groupby(['industry']).sum().sort_values(by=['last_volume'], ascending=False).reset_index()

            df_vol_data_all_industries = df_vol_data_all_industries.head(10)

            for index, row in df_vol_data_all_industries.iterrows():
                industries[row['industry']] = {'volume': row['last_volume']}

            return render_template(template, candlestick_patterns=candlestick_patterns, stocks=stocks, sectors=sectors, industries=industries, percentage=percentage_dict, pattern=pattern)

        if(pattern == 'BREAKOUT'):
            template = "breakout.html"

            consolidating = {}
            breakout = {}

            df_consolidating = load_data_from_pickle("02_consolidating")
            df_breakout = load_data_from_pickle("03_breakout")

            for index, row in df_consolidating.iterrows():
                consolidating[row['symbol']] = {'company': row['company'], 'sector': row['sector'], 'industry': row['industry'], 'last':"{:.2f}".format(row['last'])}

            for index, row in df_breakout.iterrows():
                breakout[row['symbol']] = {'company': row['company'], 'sector': row['sector'], 'industry': row['industry'], 'last':"{:.2f}".format(row['last'])}

            return render_template(template, candlestick_patterns=candlestick_patterns, consolidating=consolidating, breakout=breakout, pattern=pattern)

        if(pattern == 'EARNINGS_CALENDAR'):
            template = "calendar.html"

            df_earnings_calendar = load_data_from_pickle("04_earnings_calendar")

            result = df_earnings_calendar.to_html()

            return render_template(template, candlestick_patterns=candlestick_patterns, result=result)

        if(pattern == 'ECONOMIC_CALENDAR'):
            template = "calendar.html"

            df_economic_calendar = load_data_from_pickle("05_economic_calendar")

            result = df_economic_calendar.to_html()

            return render_template(template, candlestick_patterns=candlestick_patterns, result=result)

        if(pattern == 'INSIDER_TRADING'):
            template = "calendar.html"
            #scrape_table_insider_trades(df_tickers)
            #df_economic_calendar = load_data_from_pickle("05_economic_calendar")

            #result = df_economic_calendar.to_html()

            #return render_template(template, candlestick_patterns=candlestick_patterns, result=result)


    return render_template(template, candlestick_patterns=candlestick_patterns, pattern=pattern)
