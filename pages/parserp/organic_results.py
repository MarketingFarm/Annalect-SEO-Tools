from bs4 import BeautifulSoup
import pandas as pd
import re, os, time, shutil
from datetime import datetime
from datetime import timedelta
import streamlit as st
import __main__

output_files = 'output_data'
file_organic_results = 'organic_results.csv'


def get_organic_results(soup):
    position = 1
    div_obj = {}
    div_obj['Keyword'] = []
    div_obj['Position'] = []
    div_obj['Titles'] = []
    div_obj['Links'] = []

    # creazione sezione con risultati organici
    html_organic_results = soup.find("div", {"id": "rso"})
    #print(html_organic_results)

    # rimozione dei div con class="g" duplicati
    if html_organic_results.find('div',class_='kno-kp') is not None:
        html_organic_results.find('div',class_='kno-kp').decompose()
    if html_organic_results.find('div',class_='mnr-c') is not None:
        html_organic_results.find('div',class_='mnr-c').decompose()
    if html_organic_results.find('div',class_='ULSxyf') is not None:
        html_organic_results.find('div',class_='ULSxyf').decompose()
    if html_organic_results.find('div',class_='mod') is not None:
        html_organic_results.find('div',class_='mod').decompose()
    #print(html_organic_results)

    # estrazione dati
    organic_results = html_organic_results.find_all('div',class_='g')
    #print(organic_results)

    for organic_result in organic_results:
        # with open('test.txt', 'a', encoding='utf-8') as f:
        #     f.write(organic_result.prettify())
        if organic_result.find('h3') is not None:

            keyword = soup.find('title').text.strip().split('-')[0]
            keyword = keyword.rstrip()
            #print(keyword)
            div_obj['Keyword'].append(keyword)
            # posizione + 1
            div_obj['Position'].append(position)
            #print(position)
            position +=1
            title = organic_result.find('h3').text.strip()
            title = re.sub("\s+", " ", title)
            #print(title)
            div_obj['Titles'].append(title)
            link = organic_result.find('a').attrs['href']
            #print(link)
            div_obj['Links'].append(link)
        else:
            print('saltato')

    #print(div_obj)
    div_obj_df = pd.DataFrame(div_obj, index=None)
    #print(div_obj_df)
    #div_obj_df.to_csv(f'{output_files}/{dt_string}-{file_organic_results}', mode='a', header=False, index=False, encoding='UTF-8', sep='\t')
    #print('---- organic_results')
    div_obj_df_organico = div_obj_df
    return div_obj_df_organico
