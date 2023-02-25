import os,csv
import glob
import pickle
import pandas as pd

def is_consolidating(df, percentage=2):
    recent_candlesticks = df[-15:]

    max_close = recent_candlesticks['Close'].max()
    min_close = recent_candlesticks['Close'].min()

    threshold = 1 - (percentage / 100)
    if min_close > (max_close * threshold):
        return True        

    return False

def is_breaking_out(df, percentage=2.5):
    last_close = df[-1:]['Close'].values[0]

    if is_consolidating(df[:-1], percentage=percentage):
        recent_closes = df[-16:-1]

        if last_close > recent_closes['Close'].max():
            return True

    return False

def get_data():
    list_of_files = glob.glob('datasets/*.csv',) # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    latest_file = latest_file.replace("datasets\\", "")    

    data_tickers =  {'ticker': [],'company': [], 'sector': [], 'industry': [], 'shares_outstanding': [],'last_volume': [], 'vs_avg_vol_10d': [], 'vs_avg_vol_3m': [], 'outlook': [],  'percentage': []}
    
    df_tickers = pd.DataFrame(data_tickers)

    header = True

    with open('datasets/{}'.format(latest_file)) as f:
        for row in csv.reader(f):
            if(header):
                header = False
                continue
            else:
                try:
                    shares_outstanding = float(row[41])

                    shares_outstanding = shares_outstanding *1000000
                except Exception as e:
                    shares_outstanding = 0

                df_tickers.loc[len(df_tickers.index)] = [row[1], row[0], row[7], row[8], shares_outstanding, 0,0,0,0,0]

    for index, row in df_tickers.iterrows():
        filename = "{}.csv".format(row['ticker'])
        try:
            df = pd.read_csv('datasets/daily/{}'.format(filename))
            df['Date'] = pd.to_datetime(df['Date'],format='%Y-%m-%d')

            symbol = row['ticker']
            company = row['company']
            sector = row['sector']
            industry = row['industry']
            shares_outstanding = row['shares_outstanding']

            df_10d = df.tail(10)
            df_3m = df.tail(30)

            avg_vol_10d = df_10d['Volume'].mean()
            avg_vol_3m = df_3m['Volume'].mean()
            last_volume = df.tail(1)['Volume'].values[0]

            prev_close = df[-2:-1]['Adj Close'].values[0]
            last_close = df[-1:]['Adj Close'].values[0]

            #Create calculated metrics
            if(last_volume > 0 and shares_outstanding > 0):
                percentage = last_volume/shares_outstanding
            else:
                percentage = 0

            if(last_volume > 0 and avg_vol_10d > 0):
                vs_avg_vol_10d = last_volume/avg_vol_10d
            else:
                vs_avg_vol_10d = 0

            if(last_volume > 0 and avg_vol_3m > 0):
                vs_avg_vol_3m = last_volume/avg_vol_3m
            else:
                vs_avg_vol_3m = 0

            if(last_close > prev_close):
                outlook = 'bullish'
            else:
                outlook = 'bearish'

            df_tickers.loc[df_tickers["ticker"] == symbol, "last_volume"] = last_volume
            df_tickers.loc[df_tickers["ticker"] == symbol, "vs_avg_vol_10d"] = vs_avg_vol_10d
            df_tickers.loc[df_tickers["ticker"] == symbol, "vs_avg_vol_3m"] = vs_avg_vol_3m
            df_tickers.loc[df_tickers["ticker"] == symbol, "outlook"] = outlook
            df_tickers.loc[df_tickers["ticker"] == symbol, "percentage"] = percentage

        except Exception as e:
            print('failed on filename: ', filename)

    #pickle the data

    pickle_out = open("tickers.pickle", "wb")
    pickle.dump(df_tickers,pickle_out)
    pickle_out.close()

    return df_tickers

def load_data_from_pickle():

    pickle_in = open("tickers.pickle","rb")
    df_tickers = pickle.load(pickle_in)

    return df_tickers
