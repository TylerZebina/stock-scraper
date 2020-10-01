from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium import webdriver
import chromedriver_binary
import smtplib
import time
import json
import re

class Notifier:
    def __init__(self, smtp_host: str, smtp_port: int, sender_address: str, sender_password: str, recipients: list):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

        self.sender_address = sender_address
        self.sender_password = sender_password
        self.recipients = recipients

        self.start_server()
    
    def start_server(self):
        """
        Starts a new SMTP server using smtp_host and smtp_port.
        Logs in to server using sender_address and sender_password.
        """
        self.server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        self.server.starttls()
        self.server.login(self.sender_address, self.sender_password)

    def stop_server(self):
        """
        Closes SMTP server.
        """
        self.server.close()

    def send_notification(self, subject: str, body: str):
        """
        Sends notification to all recipients.
        """
        for recipient_address in self.recipients:
            message = ("From: %s\r\n" % self.sender_address
                + "To: %s\r\n" % recipient_address
                + "Subject: %s\r\n" % subject
                + "\r\n"
                + body)

            self.server.sendmail(self.sender_address, recipient_address, message)

class Scraper:
    def __init__(self, domains: dict):
        self.domains = domains

        self.start_driver()

    def delete_cookies(self):
        """
        Deletes cookies from webdriver.
        """
        self.driver.delete_all_cookies()

    def check_stock(self, link: str) -> bool:
        """
        Returns True if the link contains the goal class/id/value for a domain.

        Creates a soup of the loaded page source for a link, then searches that soup
        using the class, id, and value of the domain.
        """
        soup = BeautifulSoup(self.get_loaded_page(link), "lxml")
        domain_name = urlparse(link).netloc

        domain = self.domains.get(domain_name)
        if domain:
            if not (domain.class_ or domain.id_ or domain.value_):
                print("You must provide at least one class, id, or string value to search for on " + domain_name)
                return False
            
            # search by class or id if provided
            if soup and domain.class_:
                soup = soup.find(class_=domain.class_)
            elif soup and domain.id_:
                soup = soup.find(id=domain.id_)

            # search by value if provided
            if soup and domain.value_:
                soup = soup.find(text=re.compile(domain.value_))
            
            return soup != None
        
        print("Search information for domain: " + domain_name + " not provided.")
        return False

    def start_driver(self):
        """
        Starts Chrome webdriver with specified options.
        """
        options = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        # options.add_argument("--headless")
        # options.add_argument('--ignore-certificate-errors')
        # options.add_argument('--ignore-ssl-errors')
        # options.add_argument('--ignore-certificate-errors-spki-list')
        # options.add_argument("--disable-popup-blocking")
        options.add_argument("log-level=3")
        self.driver = webdriver.Chrome(options=options)

    def stop_driver(self):
        """
        Quits webdriver.
        """
        self.driver.quit()

    def get_loaded_page(self, link: str, sleep_time: int = 2) -> str:
        """
        Return loaded page source as a string.
        
        Continues to load page until page hash does not change.
        """
        def get_page_hash():
            dom = self.driver.find_element_by_tag_name("html").get_attribute("innerHTML")
            dom_hash = hash(dom.encode("utf-8"))
            return dom_hash

        page_hash = "empty"
        page_hash_new = ""

        self.driver.get(link)
        # comparing old and new page DOM hash together to verify the page is fully loaded
        while page_hash != page_hash_new: 
            page_hash = get_page_hash()
            time.sleep(sleep_time)
            page_hash_new = get_page_hash()
        
        return self.driver.page_source

class Domain:
    def __init__(self, class_: str, id_: str, value_: str):
        self.class_ = class_
        self.id_ = id_
        self.value_ = value_

def extract_domains(domain_dict: dict) -> dict:
    """
    Converts all dicts in "domains" to Domain type and returns new domain dictionary.
    """
    for key in domain_dict:
        val = domain_dict[key]
        try:
            domain_dict[key] = Domain(val["class_"], val["id_"], val["value_"])
            # convert value_ to regex pattern
            if domain_dict[key].value_ != None:
                domain_dict[key].value_ = re.compile(".*" + domain_dict[key].value_ + ".*")
        except KeyError:
            print("Domain formatting error in pages.json.")
    
    return domain_dict

def main():
    # setup using json data
    f = open("info.json")
    info = json.load(f)
    f.close()

    f = open("pages.json")
    pages = json.load(f)
    f.close()

    try:
        links = pages["links"]
        domains = extract_domains(pages["domains"])
    except KeyError:
        print("Missing or modified key name in pages.json.")

    try:
        sender_address = info["sender_address"]
        sender_password = info["sender_password"]
        recipients = info["recipients"]
        smtp_host = info["smtp_host"]
        smtp_port = info["smtp_port"]
    except KeyError:
        print("Missing or modified key name in info.json.")
    

    # create a notifier for sending notifications and scraper for checking stock of pages
    notifier = Notifier(smtp_host, smtp_port, sender_address, sender_password, recipients)
    scraper = Scraper(domains)


    # search through every page, deleting cookies after all pages have been traversed
    while True:
        for link in links:
            if scraper.check_stock(link):
                notifier.send_notification("Stock Alert", link)
                print("\033[92m" + "IN STOCK: " + link)
            else:
                print("\033[91m" + "Out of Stock: " + link)
        scraper.delete_cookies()

if __name__ == "__main__":
    main()