from bs4 import BeautifulSoup
import pandas as pd
import re, os, time, shutil
from datetime import datetime
from datetime import timedelta
import streamlit as st
import __main__

output_files = 'output_data'
file_related_searches = 'related_searches.csv'


def get_related_searches(soup):
    div_obj = {}
    div_obj['Keyword'] = []
    div_obj['Query'] = []
    div_obj['Link'] = []


    # creazione sezione con risultati correlati
    #html_related_searches = soup.find("div", {"class": "card-section"})
    html_related_searches = soup.find("div", {"id": "botstuff"})

    if html_related_searches.find('div',class_='card-section') is not None:
        html_related_searches = html_related_searches.find("div", {"class": "card-section"})
        #print('card-section trovato')
    else:
        html_related_searches = soup.find("div", {"id": "botstuff"})



    # # rimozione dei div non pertinenti
    # if html_related_searches.find('div',class_='obcontainer') is not None:
    #     html_related_searches.find('div',class_='obcontainer').decompose()
    if html_related_searches.find('div',class_='mnr-c') is not None:
        html_related_searches.find('div',class_='mnr-c').decompose()
    if html_related_searches.find('div',class_='lgJJud') is not None:
        html_related_searches.find('div',class_='lgJJud').decompose()
    

    #print(html_relate)
    related_queries = html_related_searches.find_all('a')
    #print(related_queries)
    for related_query in related_queries:
        keyword = soup.find('title').text.strip().split('-')[0]
        #print(keyword)
        div_obj['Keyword'].append(keyword)
        query = re.sub(' +',' ',related_query.text.strip().replace('\n',''))
        #print(query)
        div_obj['Query'].append(query)
        link = related_query.attrs['href']
        #print(link)
        div_obj['Link'].append(link)
    #print(div_obj)
    div_obj_df = pd.DataFrame(div_obj, index=None)
    #print(div_obj_df)
    #now = datetime.now()
    #dt_string = now.strftime("%Y%m%d-%H")
    #div_obj_df.to_csv(f'{output_files}/{dt_string}-{file_related_searches}', mode='a', header=False, index=False, encoding='UTF-8', sep='\t')
    #print('---- related_searches')
    div_obj_df_correlate = div_obj_df
    return div_obj_df_correlate
