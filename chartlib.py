#import os,csv
#import glob
import re
import pickle
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def get_page(url):
  # When website blocks your request, simulate browser request: https://stackoverflow.com/questions/56506210/web-scraping-with-python-problem-with-beautifulsoup
  header={'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36'}
  page = requests.get(url=url,headers=header)

  try:
      page.raise_for_status()
  except requests.exceptions.HTTPError as e:
      # Whoops it wasn't a 200
      raise Exception("Http Response (%s) Is Not 200: %s" % (url, str(page.status_code)))

  return page


def get_page_selenium(url):

  #Selenium Browser Emulation Tool
  chrome_options = Options()
  chrome_options.add_argument("--headless")
  chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 640 XL LTE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10166")


  driver = webdriver.Chrome(ChromeDriverManager().install(),options=chrome_options)
  driver.get(url)
  driver.implicitly_wait(10)  
  time.sleep(5)
  html = driver.page_source
  driver.close()
  
  return html

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

# Swap function
def swapPositions(list, pos1, pos2):
     
    list[pos1], list[pos2] = list[pos2], list[pos1]
    return list

# Function to clean the names
def clean_dates(date_name):
    pattern_regex = re.compile(r'^(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)')
    day_of_week = re.search(pattern_regex,date_name).group(0)

    pattern_regex = re.compile(r'[0-9][0-9]')
    day_of_month = re.search(pattern_regex,date_name).group(0)

    pattern_regex = re.compile(r'(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)')
    month_of_year = re.search(pattern_regex,date_name).group(0)

    formatted_date_string = "%s %s %s" % (day_of_week, day_of_month, month_of_year)

    return formatted_date_string


def get_ticker_data(df_tickers):

    for index, row in df_tickers.iterrows():
        filename = "{}.csv".format(row['ticker'])
        try:
            df = pd.read_csv('datasets/daily/{}'.format(filename))
            df['Date'] = pd.to_datetime(df['Date'],format='%Y-%m-%d')

            symbol = row['ticker']
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
            df_tickers.loc[df_tickers["ticker"] == symbol, "last"] = last_close

        except Exception as e:
            print('failed on filename: ', filename)

    #pickle the data
    pickle_out = open("01_tickers.pickle", "wb")
    pickle.dump(df_tickers,pickle_out)
    pickle_out.close()

    return df_tickers

def get_breakout_data(df_tickers):
    data =  {'symbol': [],'company': [], 'sector': [], 'industry': [] , 'last': []}
    
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
            last = row['last']
        
            if is_consolidating(df, percentage=2.5):
                df_consolidating.loc[len(df_consolidating.index)] = [symbol, company, sector, industry, last]

            if is_breaking_out(df):
                df_breakout.loc[len(df_breakout.index)] = [symbol, company, sector, industry, last]

        except Exception as e:
            print('failed on filename: ', filename)

    #pickle the data
    pickle_out = open("02_consolidating.pickle", "wb")
    pickle.dump(df_consolidating,pickle_out)
    pickle_out.close()

    #pickle the data
    pickle_out = open("03_breakout.pickle", "wb")
    pickle.dump(df_breakout,pickle_out)
    pickle_out.close()

    return True

def scrape_table_earningswhispers_earnings_calendar(df_us_companies):
    print("Getting data from Earnings Whispers")

    df = pd.DataFrame()

    # Get earnings calendar for the next fortnight
    for x in range(1, 16):
        print("Day %s" % x)
        earnings_whispers_day_df = scrape_earningswhispers_day(x, df_us_companies)
        df = df.append(earnings_whispers_day_df, ignore_index=True)

    df = df.drop_duplicates(subset='Ticker', keep="first")

    #pickle the data
    pickle_out = open("04_earnings_calendar.pickle", "wb")
    pickle.dump(df,pickle_out)
    pickle_out.close()

    return True

def scrape_earningswhispers_day(day, df_us_companies):
    url = "https://www.earningswhispers.com/calendar?sb=c&d=%s&t=all" % (day,)
    #df_us_companies = get_zacks_us_companies()
    page = get_page_selenium(url)
    #import pdb;  pdb.set_trace()

    #soup = BeautifulSoup(page.content, 'html.parser')
    soup = BeautifulSoup(page, 'html.parser')

    date_str = soup.find('div', attrs={"id":"calbox"})
    date_str = date_str.text.strip().replace('for ','')

    eps_cal_table = soup.find('ul', attrs={"id":"epscalendar"})

    table_rows = eps_cal_table.find_all('li')

    df = pd.DataFrame()
    
    # Add Date, Time, CompanyName, Ticker headers to dataframe
    df.insert(0,"Date",[],True)
    df.insert(1,"Time",[],True)
    df.insert(2,"Ticker",[],True)
    df.insert(3,"Company Name",[],True)
    #df.insert(4,"Market Cap (Mil)",[],True)
    #df.insert(5,"EPS",[],True)
    #df.insert(6,"Revenue",[],True)
    #df.insert(7,"Expected Revenue Growth",[],True)

    skip_first = True

    for tr in table_rows:        
        temp_row = []

        td = tr.find_all('div')

        # Just Extract Date, Time, CompanyName, Ticker, EPS, Revenue, Expected Revenue
        for obs in td:  
            text = str(obs.text).strip()
            temp_row.append(text)    

        #import pdb; pdb.set_trace()
        time_str = temp_row[4]
        company_name_str = temp_row[2]
        ticker_str = temp_row[3]
        #eps = temp_row[7]
        #revenue = temp_row[8]
        #expected = temp_row[9]

        if(time_str.find(' ET') != -1):
            # Only if company exists on US stocks list, we add to df
            df_retrieved_company_data = df_us_companies.loc[df_us_companies['ticker'] == ticker_str].reset_index(drop=True)
            if(df_retrieved_company_data.shape[0] > 0):
                temp_row1 = []
                temp_row1.append(date_str)
                temp_row1.append(time_str)
                temp_row1.append(ticker_str)
                temp_row1.append(company_name_str)
                # Get market cap from US Stocks list
                #temp_row1.append(df_retrieved_company_data['MARKET_CAP'].iloc[0])
                #temp_row1.append(eps)
                #temp_row1.append(revenue)
                #temp_row1.append(expected)

                #Get EPS, Revenue and Expected Growth

                if not skip_first:   
                    df.loc[len(df.index)] = temp_row1

        skip_first = False

    return df

def scrape_table_marketscreener_economic_calendar():
    print("Getting data from Market Screener")

    url = "https://www.marketscreener.com/stock-exchange/calendar/economic/"

    page = get_page(url)
    soup = BeautifulSoup(page.content, 'html.parser')
    df = pd.DataFrame()

    tables = soup.find_all('table', recursive=True)

    table = tables[0]

    table_rows = table.find_all('tr')

    table_header = table_rows[0]
    td = table_header.find_all('th')
    index = 0

    for obs in td:        
        text = str(obs.text).strip()

        if(len(text)==0):
            text = "Date"
        df.insert(index,text,[],True)
        index+=1

    index = 0
    skip_first = True
    session = ""

    for tr in table_rows:        
        temp_row = []
        #import pdb; pdb.set_trace()
        td = tr.find_all('td')
        #class="card--shadowed"
        if not skip_first:
            td = tr.find_all('td')
            th = tr.find('th') #The time is stored as a th
            if(th):
                temp_row.append(th.text)        

            if(len(td) == 4):
                session = str(td[0].text).strip()

            for obs in td:  

                text = str(obs.text).strip()
                text = text.replace('\n','').replace('  ','')

                if(text == ''):
                    flag_class = obs.i.attrs['class'][2]
                    #Maybe this is the country field, which means that the country is represented by a flag image
                    if(flag_class == 'flag__us'):
                        text = "US"
                    elif(flag_class == 'flag__uk'): 
                        text = "UK"

                    elif(flag_class == 'flag__eu'): 
                        text = "European Union"

                    elif(flag_class == 'flag__de'): 
                        text = "Germany"

                    elif(flag_class == 'flag__jp'): 
                        text = "Japan"

                    elif(flag_class == 'flag__cn'): 
                        text = "China"
                    else:
                        text = "OTHER"
    
                temp_row.append(text)        


            pos1, pos2  = 1, 2

            if(len(temp_row) == len(df.columns)):
                temp_row = swapPositions(temp_row, pos1-1, pos2-1)
            else:
                temp_row.insert(0,session)
                #print(temp_row)
                #import pdb; pdb.set_trace()

            df.loc[len(df.index)] = temp_row
        else:
            skip_first = False

    #Remove Duplicates (Country, Events)
    df = df.drop_duplicates(subset=['Country', 'Events'])

    #Remove OTHER Countries
    df = df[df.Country != 'OTHER'].reset_index(drop=True)

    #Format Date into Date field '%A%d%B'
    #df['Date'] = pd.to_datetime(df['Date'], format='%A%d%B')
    # Updated the date columns
    df['Date'] = df['Date'].apply(clean_dates)

    #pickle the data
    pickle_out = open("05_economic_calendar.pickle", "wb")
    pickle.dump(df,pickle_out)
    pickle_out.close()

    return True


def load_data_from_pickle(name):

    pickle_file = "{}.pickle".format(name)

    pickle_in = open(pickle_file,"rb")
    df = pickle.load(pickle_in)

    return df
