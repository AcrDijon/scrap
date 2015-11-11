# -*- coding: utf-8 -*-
import itertools
import urlparse
import json
import os
import re
import urllib

from webscraping import common, download, xpath

from jinja2 import Markup
import six


DOMAIN = 'http://acr.dijon.over-blog.com/'
#writer = common.UnicodeWriter('articles.csv')
#writer.writerow(['Title', 'Num reads', 'URL'])
seen_urls = set() # track which articles URL's already seen, to prevent duplicates
D = download.Download(cache_file='cache')

years = range(2005, 2016)
root = 'archive/%d-%.2d/'
articles = []

def load_list():
    if os.path.exists('articles.json'):
        with open('articles.json') as f:
            return json.loads(f.read())

    for year in years:
        print('Listing %d' % year)
        for month in range(1, 13):
            page = root % (year, month)
            url = urlparse.urljoin(DOMAIN, page)
            archive = D.get(url)

            for path in ('//li[@class="listArticles  article_item_even"]/a/@href',
                        '//li[@class="listArticles  article_item_odd"]/a/@href'):

                articles.extend(xpath.search(archive, path))

    with open('articles.json', 'w') as f:
        f.write(json.dumps(articles))


def slugify(value, substitutions=()):
    value = Markup(value).striptags()
    import unicodedata
    from unidecode import unidecode
    value = unidecode(value)
    if isinstance(value, six.binary_type):
        value = value.decode('ascii')
    # still unicode
    value = unicodedata.normalize('NFKD', value).lower()
    for src, dst in substitutions:
        value = value.replace(src.lower(), dst.lower())
    value = re.sub('[^\w\s-]', '', value).strip()
    value = re.sub('[-\s]+', '-', value)
    value = value.encode('ascii', 'ignore')
    return value.decode('ascii')


TMP = u"""\
%(title)s
%(title_under)s

:date: %(date)s
:category: Résultats
:summary: %(title)s

%(content)s
"""

articles = load_list()
image_dir = 'images'


for article in articles:
    page = D.get(article)
    if not page:
        print('Failed on %s' % article)
        continue

    page = page.decode('utf8')
    data = {}
    data['title'] = xpath.search(page, '//a[@class="titreArticle"]')[0]

    data['title_under'] = '=' * len(data['title'])
    content = xpath.search(page,
            '//div[@class="contenuArticle"]')[0].strip()


    day = int(xpath.search(page, '//span[@class="day"]')[0])
    month = int(xpath.search(page, '//span[@class="month"]')[0][-2:])
    year = int(xpath.search(page, '//span[@class="year"]')[0][-4:])
    hour = xpath.search(page, '//span[@class="hour"]')[0]
    date = '%d-%d-%d %s' % (year, month, day, hour)
    data['date'] = date
    name = slugify(date + '-' + data['title']) + '.md'
    filename = os.path.join('archives', name)
    if os.path.exists(filename):
        continue


    # images in the content
    images = xpath.search(page, '//img/@src')
    images = [image for image in images if image in content]
    for image in images:
        i_filename = os.path.split(image)[-1]
        local_name = slugify(date + '-' + i_filename)
        content = content.replace(image, '/' + local_name)
        disk_name = os.path.join(image_dir, local_name)
        if os.path.exists(disk_name):
            continue
        try:
            urllib.urlretrieve(image, filename=disk_name)
        except IOError:
            print('Image does not exist anymore ' + image)
            continue
        print('Downloading %s' % image)

    data['content'] = content
    print('Writing %s' % filename)
    page = TMP % data
    with open(filename, 'w') as f:
        f.write(page.encode('utf8'))
