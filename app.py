import os, csv
from datetime import datetime, date, timedelta
import glob
import yfinance as yf
import pandas as pd
from flask import Flask, escape, request, render_template
from patterns import candlestick_patterns

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

    data_tickers =  {'ticker': [],'company': [], 'sector': [], 'industry': []}
    data_stock_volume = {'ticker': [],'company': [],'last_volume': [], 'vs_avg_vol_10d': [], 'vs_avg_vol_3m': [], 'outlook': [], 'sector': [], 'industry': []}
    
    df_tickers = pd.DataFrame(data_tickers)
    df_stock_volume = pd.DataFrame(data_stock_volume)

    header = True

    with open('datasets/{}'.format(latest_file)) as f:
        for row in csv.reader(f):
            #import pdb;  pdb.set_trace()
            if(header):
                header = False
                continue
            else:
                df_tickers.loc[len(df_tickers.index)] = [row[1], row[0], row[7], row[8]]

                #stocks[row[1]] = {'company': row[0]}
                #import pdb; pdb.set_trace()
                #df = pd.read_csv('datasets/daily/{}'.format(filename))
    #import pdb; pdb.set_trace()
    if pattern:
        if(pattern == 'VOLUME'):
            template = "volume.html"
            for index, row in df_tickers.iterrows():
                filename = "{}.csv".format(row['ticker'])
                try:
                    df = pd.read_csv('datasets/daily/{}'.format(filename))
                    df['Date'] = pd.to_datetime(df['Date'],format='%Y-%m-%d')

                    symbol = row['ticker']
                    company = row['company']
                    sector = row['sector']
                    industry = row['industry']
                
                    df_10d = df.tail(10)
                    df_3m = df.tail(30)

                    avg_vol_10d = df_10d['Volume'].mean()
                    avg_vol_3m = df_3m['Volume'].mean()
                    last_volume = df.tail(1)['Volume'].values[0]
                    #import pdb; pdb.set_trace()
                    prev_close = df[-2:-1]['Adj Close'].values[0]
                    last_close = df[-1:]['Adj Close'].values[0]

                    #Create calculated metrics
                    vs_avg_vol_10d = last_volume/avg_vol_10d
                    vs_avg_vol_3m = last_volume/avg_vol_3m
                    
                    if(last_close > prev_close):
                        outlook = 'bullish'
                    else:
                        outlook = 'bearish'
                                            
                    df_stock_volume.loc[len(df_stock_volume.index)] = [symbol, company, last_volume, vs_avg_vol_10d, vs_avg_vol_3m, outlook, sector, industry]

                except Exception as e:
                    print('failed on filename: ', filename)
            df_stock_volume = df_stock_volume.sort_values(by=['vs_avg_vol_3m'], ascending=False)        

            for index, row in df_stock_volume.iterrows():
                stocks[row['ticker']] = {'company': row['company'], 'vs_avg_vol_10d': "{:.2%}".format(row['vs_avg_vol_10d']),'vs_avg_vol_3m': "{:.2%}".format(row['vs_avg_vol_3m']), 'pattern': row['outlook'], 'sector': row['sector'], 'industry': row['industry']}

            #data_stock_volume = {'ticker': [],'company': [],'last_volume': [], 'vs_avg_vol_10d': [], 'vs_avg_vol_3m': [], 'outlook': [], 'sector': [], 'industry': []}

            df_vol_data_all_sectors = df_stock_volume.drop(['company','ticker','industry','vs_avg_vol_10d','vs_avg_vol_3m', 'outlook'], axis=1)
            #import pdb; pdb.set_trace()
            df_vol_data_all_sectors = df_vol_data_all_sectors.groupby(['sector']).sum().sort_values(by=['last_volume'], ascending=False).reset_index()

            df_vol_data_all_sectors = df_vol_data_all_sectors.head(5)

            for index, row in df_vol_data_all_sectors.iterrows():
                sectors[row['sector']] = {'volume': row['last_volume']}

            df_vol_data_all_industries = df_stock_volume.drop(['company','ticker','sector','vs_avg_vol_10d','vs_avg_vol_3m', 'outlook'], axis=1)
            df_vol_data_all_industries = df_vol_data_all_industries.groupby(['industry']).sum().sort_values(by=['last_volume'], ascending=False).reset_index()

            df_vol_data_all_industries = df_vol_data_all_industries.head(10)

            for index, row in df_vol_data_all_industries.iterrows():
                industries[row['industry']] = {'volume': row['last_volume']}

       #import pdb; pdb.set_trace()            
    return render_template(template, candlestick_patterns=candlestick_patterns, stocks=stocks, sectors=sectors, industries=industries, pattern=pattern)
