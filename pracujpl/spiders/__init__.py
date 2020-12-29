import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import scrapy

from pracujpl import settings

# CONSTANTS
PRACUJPL_LINK_WITH_SOME_FILTERS = 'https://www.pracuj.pl/praca/doradca%20klienta%20w%20banku-x44-praca%20w%20banku-x44-doradca%20klienta;kw/szczecin;wp/ing%20bank%20%c5%9bl%c4%85ski%20s.a.;en?rd=15&tc=0&ws=0'
DATE_FORMAT = '{:%Y-%m-%d %H:%M}'.format(datetime.now())

# JSON RELATED CONSTANTS
JSON_DUMP_FILE_NAME = 'dumped_hrefs.json'
JSON_HREF_LINKS_KEY = 'json_href_links'


# gets job href links as response css selector
def get_job_link_hrefs(parsed_html_response: scrapy.http.response) -> list:
    return parsed_html_response.css('div.offer__click a::attr(href)').getall()


# creates mail message relies on data filtered from json file
def create_mail_message(href_links: set) -> str:
    msg = MIMEMultipart()
    msg['Subject'] = "Pracujpl__ING-Bank oferta pracy dla kociaka:))"
    msg.attach(MIMEText('\n'.join(
        href_links
    )))

    return msg.as_string()


# saves job href links as json file
def save_unique_href_links_as_json(new_href_links: set):
    with open(JSON_DUMP_FILE_NAME, 'w') as json_dump:
        json.dump({JSON_HREF_LINKS_KEY: list(new_href_links)}, json_dump)

    print(f'Saved new href links to json format at {DATE_FORMAT}!')


# gets href links array fetched previously from json file
def get_existing_href_links_from_json() -> list:
    if not os.path.exists(os.path.join(os.getcwd(), JSON_DUMP_FILE_NAME)):
        save_unique_href_links_as_json(set())

    with open(JSON_DUMP_FILE_NAME) as json_dump:
        return json.load(json_dump)[JSON_HREF_LINKS_KEY]


# gets only unique href links by diffing sets
def get_unique_href_links(fetched_previously: set, filtered_actual: set) -> set:
    return filtered_actual \
        .difference(fetched_previously)


class PracujplSpider(scrapy.Spider):
    name = settings.BOT_NAME

    def start_requests(self):
        urls = [
            PRACUJPL_LINK_WITH_SOME_FILTERS
        ]

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response, **kwargs):
        fetched_previously_href_links = set(get_existing_href_links_from_json())

        only_unique_href_links = get_unique_href_links(
            fetched_previously_href_links,
            set([href for href in get_job_link_hrefs(response) if re.search('ing bank', href)])
        )

        if only_unique_href_links:
            send_email(
                only_unique_href_links, fetched_previously_href_links
            )
        else:
            self.log(f'There are no new offers. Crawler invoked at {DATE_FORMAT}!')


def send_email(only_unique_href_links: set, fetched_previously_href_links: set):
    try:
        # INITIALIZATION
        with smtplib.SMTP('smtp.gmail.com:587') as smtp_server:
            smtp_server.ehlo()
            smtp_server.starttls()

            # LAUNCH LOGIN TO SMTP SERVER WITH AUTHENTICATION
            smtp_server.login(settings.HOST_MAIL_ADDRESS, settings.HOST_MAIL_PASSWORD)

            # MAJOR FUNCTION TRIGGERS MAIL SENDING
            smtp_server.sendmail(settings.HOST_MAIL_ADDRESS,
                                 settings.MARTUSIA_MAIL,
                                 create_mail_message(
                                     only_unique_href_links
                                 ))

        print('Success: mail sent!')
    except smtplib.SMTPException:
        print('Mail failed to send!')
    else:
        save_unique_href_links_as_json(
            fetched_previously_href_links.union(only_unique_href_links)
        )
