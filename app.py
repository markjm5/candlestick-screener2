import os, sys, time #csv
from datetime import datetime, date, timedelta
import glob
import json
import yfinance as yf
import pandas as pd
from flask import Flask, escape, request, render_template
from patterns import candlestick_patterns
from chartlib import is_breaking_out, is_consolidating, get_data, load_data_from_pickle #, transpose_df_string_numbers

app = Flask(__name__)

todays_date = date.today()
date_str_today = "%s-%s-%s" % (todays_date.year, todays_date.month, todays_date.day)
date_str_start = "2007-01-01"

list_of_files = glob.glob('datasets/*.csv',) # * means all if need specific format then *.csv
latest_file = max(list_of_files, key=os.path.getctime)
latest_file = latest_file.replace("datasets\\", "")

@app.route('/snapshot')
def snapshot():
    #get date range

    now_start = datetime.now()
    start_time = now_start.strftime("%H:%M:%S")    

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
                data = yf.download(symbol, start=date_str_start, end=date_str_today)
                data.to_csv('datasets/daily/{}.csv'.format(symbol))
                print(symbol)

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
        #TODO: Serealise df every day, and read from serealised object.

        pickle_file = glob.glob("*.pickle")[0]
        file_path = "%s\\%s" % (sys.path[0],pickle_file)

        ti_m = os.path.getmtime(file_path)        
        m_ti = time.ctime(ti_m)
        t_obj = time.strptime(m_ti)

        #TODO: Compare with todays_date
        dt_pickle = datetime.fromtimestamp(time.mktime(t_obj))
        timedelta = dt_pickle.date() - todays_date
        if(timedelta.days == 0):
            api_loaded_today = True
        else:
            api_loaded_today = False

        if(api_loaded_today):
            df_tickers = load_data_from_pickle()
        else:
            df_tickers = get_data()

        if(pattern == 'VOLUME'):
            template = "volume.html"

            df_stock_volume = df_tickers.sort_values(by=['vs_avg_vol_3m'], ascending=False)        
            df_stock_volume = df_stock_volume[df_stock_volume.company != '']
            df_stock_volume = df_stock_volume[df_stock_volume.vs_avg_vol_3m > 0]

            for index, row in df_stock_volume.iterrows():
                stocks[row['ticker']] = {'company': row['company'], 'vs_avg_vol_10d': "{:.2%}".format(row['vs_avg_vol_10d']),'vs_avg_vol_3m': "{:.2%}".format(row['vs_avg_vol_3m']), 'pattern': row['outlook'], 'sector': row['sector'], 'industry': row['industry']}

            df_percentage = df_stock_volume.sort_values(by=['percentage'], ascending=False).reset_index() 
            df_percentage = df_percentage.drop(['vs_avg_vol_10d','vs_avg_vol_3m'], axis=1)
            df_percentage = df_percentage[df_percentage.percentage > 0.05]

            for index, row in df_percentage.iterrows():
                percentage_dict[row['ticker']] = {'company': row['company'],'pattern': row['outlook'], 'sector': row['sector'], 'industry': row['industry'], 'percentage':  "{:.2%}".format(row['percentage'])}

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
            
            data =  {'symbol': [],'company': [], 'sector': [], 'industry': []}
            
            df_consolidating = pd.DataFrame(data)
            df_breakout = pd.DataFrame(data)

            for index, row in df_tickers.iterrows():
                filename = "{}.csv".format(row['ticker'])

                try:
                    df = pd.read_csv('datasets/daily/{}'.format(filename))

                    symbol = row['ticker']
                    company = row['company']
                    sector = row['sector']
                    industry = row['industry']
                
                    if is_consolidating(df, percentage=2.5):
                        df_consolidating.loc[len(df_consolidating.index)] = [symbol, company, sector, industry]

                    if is_breaking_out(df):
                        df_breakout.loc[len(df_breakout.index)] = [symbol, company, sector, industry]

                except Exception as e:
                    print('failed on filename: ', filename)

            for index, row in df_consolidating.iterrows():
                consolidating[row['symbol']] = {'company': row['company'], 'sector': row['sector'], 'industry': row['industry']}

            for index, row in df_breakout.iterrows():
                breakout[row['symbol']] = {'company': row['company'], 'sector': row['sector'], 'industry': row['industry']}

            return render_template(template, candlestick_patterns=candlestick_patterns, consolidating=consolidating, breakout=breakout, pattern=pattern)

    return render_template(template, candlestick_patterns=candlestick_patterns, pattern=pattern)
