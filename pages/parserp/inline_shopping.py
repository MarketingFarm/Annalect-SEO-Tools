from bs4 import BeautifulSoup
import pandas as pd
import re, os, time, shutil
from datetime import datetime
from datetime import timedelta
import streamlit as st
import __main__

output_files = 'output_data'
file_inline_shopping = 'inline_shopping.csv'


def get_inline_shopping(soup):
    position = 1
    div_obj = {}
    div_obj['Keyword'] = []
    div_obj['Position'] = []
    div_obj['Titles'] = []
    div_obj['Merchant'] = []
    div_obj['Price'] = []
    div_obj['Value'] = []
    #div_obj['Currency'] = []
    div_obj['Link'] = []

    #soup = soup_from_file(f'{html_file}/{file}'.format(file=file,html_file=html_file))
    html_inline_shopping = soup.find("div", {"class": "cu-container"})
    #print(html_inline_shopping)
    inline_shoppings = html_inline_shopping.find_all('div',class_=['mnr-c', 'pla-unit'])
    #print(inline_shoppings)

    for inline_shopping in inline_shoppings:
        keyword = soup.find('title').text.strip().split('-')[0]
        #print(keyword)
        div_obj['Keyword'].append(keyword)
        #posizione + 1
        div_obj['Position'].append(position)
        #print(position)
        position +=1
        title = inline_shopping.find('a', {'class' : 'plantl pla-unit-title-link'}).text.strip()
        title = re.sub(' +',' ',title.replace('\n',''))
        title = title[:len(title)//2]
        #print(title)
        div_obj['Titles'].append(title)
        merchant = inline_shopping.find('div', {'class' : 'LbUacb'}).text.strip()
        merchant = re.sub(' +',' ',merchant.replace('\n',''))
        merchant = merchant[:len(merchant)//2]
        #print(merchant)
        div_obj['Merchant'].append(merchant)
        price = inline_shopping.find('div', {'class' : 'e10twf T4OwTb'}).text.strip()
        price = re.sub(' +',' ',price.replace('\n',''))
        #print(price)
        div_obj['Price'].append(price)
        only_value = price.replace(",", ".")
        value_comma = re.sub(r"[^\d\.]", "", only_value)
        value = value_comma.replace(".", ",")
        #print(value)
        div_obj['Value'].append(value)
        #currency = re.sub('[^a-zA-Z]+', '', price)
        #print(currency)
        #div_obj['Currency'].append(currency)
        link = inline_shopping.find('a', {'class' : 'plantl'}).attrs['href']
        #print(link)
        div_obj['Link'].append(link)
    #print(div_obj)
    div_obj_df = pd.DataFrame(div_obj, index=None)
    #print(div_obj_df)
    now = datetime.now()
    dt_string = now.strftime("%Y%m%d-%H")
    div_obj_df.to_csv(f'{output_files}/{dt_string}-{file_inline_shopping}', mode='a', header=False, index=False, encoding='UTF-8', sep=';')
    print('---- inline_shopping')
