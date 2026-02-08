# import feedparser
from bs4 import BeautifulSoup
import urllib
from dateparser import parse as parse_date
import requests
import ssl
import certifi
from urllib.parse import urlparse
from bs4 import BeautifulSoup

class GoogleNews:
    def __init__(self, lang='en', country='US'):
        self.lang = lang.lower()
        self.country = country.upper()
        self.BASE_URL = 'https://news.google.com/rss'

    def __custom_parser(self,xml_text):
            soup = BeautifulSoup(xml_text, 'xml')
            entries = []

            for item in soup.find_all('item'):
                title = item.title.text if item.title else ''
                link = item.link.text if item.link else ''
                pub_date = item.pubDate.text if item.pubDate else ''

                entries.append({
                    'title': title,
                    'link': link,
                    'published': pub_date
                })

            return {
                'feed': {},        # Optional: can add metadata here if needed
                'entries': entries
            }


    def __get_certificate_pem(self,hostname, port=443, cert_file='server_cert.pem'):
        cert = ssl.get_server_certificate((hostname, port))
        with open(cert_file, 'w') as f:
            f.write(cert)
        return cert_file


    def __combine_cert_with_certifi(self,cert_file, combined_file='combined.pem'):
        with open(certifi.where(), 'rb') as base, open(cert_file, 'rb') as site:
            combined = base.read() + b'\n' + site.read()
        with open(combined_file, 'wb') as f:
            f.write(combined)
        return combined_file


    def __top_news_parser(self, text):
        """Return subarticles from the main and topic feeds"""
        try:
            bs4_html = BeautifulSoup(text, "html.parser")
            lis = bs4_html.find_all('li')
            sub_articles = []
            for li in lis:
                try:
                    sub_articles.append({
                        "url": li.a['href'],
                        "title": li.a.text,
                        "publisher": li.font.text
                    })
                except:
                    pass
            return sub_articles
        except:
            return text

    def __ceid(self):
        """Compile correct country-lang parameters for Google News RSS URL"""
        return f'?ceid={self.country}:{self.lang}&hl={self.lang}&gl={self.country}'

    def __add_sub_articles(self, entries):
        for i, val in enumerate(entries):
            if 'summary' in entries[i].keys():
                entries[i]['sub_articles'] = self.__top_news_parser(entries[i]['summary'])
            else:
                entries[i]['sub_articles'] = None
        return entries

    def __parse_feed(self, feed_url, proxies=None, scraping_bee=None):
        # hostname = urlparse(feed_url).hostname
        if scraping_bee and proxies:
            raise Exception("Pick either ScrapingBee or proxies. Not both!")

        if proxies:
            hostname = urlparse(feed_url).hostname
            site_cert = self.__get_certificate_pem(hostname)
            combined_cert = self.__combine_cert_with_certifi(site_cert)
            r = requests.get(feed_url,proxies=proxies,verify=combined_cert)
            # r = requests.get(feed_url, proxies=proxies, verify=False)
        else:
            hostname = urlparse(feed_url).hostname
            site_cert = self.__get_certificate_pem(hostname)
            combined_cert = self.__combine_cert_with_certifi(site_cert)
            r = requests.get(feed_url,verify=combined_cert)
            # r = requests.get(feed_url, verify=False)

        if scraping_bee:
            r = self.__scaping_bee_request(url=feed_url, api_key=scraping_bee)
        else:
            hostname = urlparse(feed_url).hostname
            site_cert = self.__get_certificate_pem(hostname)
            combined_cert = self.__combine_cert_with_certifi(site_cert)
            r = requests.get(feed_url,verify=combined_cert)
            # r = requests.get(feed_url, verify=False)

        if 'https://news.google.com/rss/unsupported' in r.url:
            raise Exception('This feed is not available')

        # d = feedparser.parse(r.text)
        d=self.__custom_parser(r.text)

        if not scraping_bee and not proxies and len(d) == 0:
            fallback_resp = requests.get(feed_url)
            d = self.__custom_parser(fallback_resp.text)

        return dict((k, d[k]) for k in ('feed', 'entries'))

    def __search_helper(self, query):
        return urllib.parse.quote_plus(query)

    def __from_to_helper(self, validate=None):
        try:
            validate = parse_date(validate).strftime('%Y-%m-%d')
            return str(validate)
        except:
            raise Exception('Could not parse your date')

    def top_news(self, proxies=None, scraping_bee=None):
        """Return a list of all articles from the main page of Google News"""
        d = self.__parse_feed(self.BASE_URL + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        return d

    def topic_headlines(self, topic: str, proxies=None, scraping_bee=None):
        """Return a list of all articles from the topic page of Google News"""
        if topic.upper() in ['WORLD', 'NATION', 'BUSINESS', 'TECHNOLOGY', 'ENTERTAINMENT', 'SCIENCE', 'SPORTS', 'HEALTH']:
            d = self.__parse_feed(self.BASE_URL + f'/headlines/section/topic/{topic.upper()}' + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        else:
            d = self.__parse_feed(self.BASE_URL + f'/topics/{topic}' + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)

        d['entries'] = self.__add_sub_articles(d['entries'])
        if len(d['entries']) > 0:
            return d
        else:
            raise Exception('Unsupported topic')

    def geo_headlines(self, geo: str, proxies=None, scraping_bee=None):
        """Return a list of all articles about a specific geolocation"""
        d = self.__parse_feed(self.BASE_URL + f'/headlines/section/geo/{geo}' + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        return d

    def search(self, query: str, helper=True, when=None, from_=None, to_=None, proxies=None, scraping_bee=None):
        """Return a list of all articles given a full-text search parameter"""

        if when:
            query += f' when:{when}'

        if from_ and not when:
            from_ = self.__from_to_helper(validate=from_)
            query += f' after:{from_}'

        if to_ and not when:
            to_ = self.__from_to_helper(validate=to_)
            query += f' before:{to_}'

        if helper:
            query = self.__search_helper(query)

        search_ceid = self.__ceid().replace('?', '&')

        d = self.__parse_feed(self.BASE_URL + f'/search?q={query}' + search_ceid, proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        return d
