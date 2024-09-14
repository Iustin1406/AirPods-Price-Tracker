import logging
import json
import time
from dateutil.relativedelta import relativedelta
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import List, Dict
import smtplib
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("errors.log")
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


class Engine:
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("detach", True)
        self.driver = webdriver.Chrome(options=chrome_options)

    def __del__(self):
        if hasattr(self, "driver"):
            self.driver.quit()

    def extract_data_from_altex(self) -> List[Dict[str, str]]:
        products = []  # a list of dict
        self.driver.get("https://altex.ro/cauta/?q=AirPods")
        timeout = 10
        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        spans = WebDriverWait(self.driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, "//span[contains(@class, 'Product-name Heading')]"))
        )

        for i, span in enumerate(spans, start=1):
            a_element = span.find_element(By.XPATH, "..")
            href_value = f"https://altex.ro/{a_element.get_attribute('href')}"

            price_xpath = f"//*[@id='__next']/div[2]/div[1]/main/div[2]/div[2]/div[2]/ul[2]/li[{i}]" + \
                          "/div/div[3]/div/div/span/span[1]"
            availability_xpath = f"//*[@id='__next']/div[2]/div[1]/main/div[2]/div[2]/div[2]/ul[2]/li[{i}]/div/div[2]"

            try:
                price_element = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.XPATH, price_xpath))
                )
                price_text = price_element.text

                availability = WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.XPATH, availability_xpath))
                )
                availability_text = availability.text.strip().lower()

                if not price_text or price_text == "":
                    raise ValueError("Price is missing")

                if not availability_text or "in" not in availability_text or "stoc" not in availability_text:
                    raise LookupError("Availability information is missing")

                product = {
                    "name": span.text,
                    "link": href_value,
                    "price": float(price_text.replace(".", "")) + 0.99,
                    "date": datetime.now().strftime('%Y-%m-%d')
                }
                if "Casti" in product["name"]:
                    products.append(product)
            except ValueError as ve:
                logger.error(f"For product {span.text} :price error: {ve}")
            except LookupError as le:
                logger.error(f"For product {span.text} :availability error: {le}")
            except Exception as e:
                logger.error(f"For product {span.text} :could not find element for item: {e}")

        return products

    def extract_data_from_flanco(self) -> List[Dict[str, str]]:
        self.driver.get("https://www.flanco.ro/catalogsearch/result/?q=casti+apple+airpods")

        timeout = 10
        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        h2_elements = self.driver.find_elements(By.TAG_NAME, "h2")
        products_name = [name.text for name in h2_elements]

        price_spans = self.driver.find_elements(By.CSS_SELECTOR, "span.singlePrice, span.special-price")
        prices = [price.text for price in price_spans]

        link_elements = self.driver.find_elements(By.CSS_SELECTOR, "a.product-item-link")
        links = []
        for link in link_elements:
            if not link.get_attribute("href") in links:
                links.append(link.get_attribute("href"))

        availability_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.stocky-txt")
        availability = [av.text for av in availability_elements]

        products = []
        if len(products_name) == len(prices) == len(links) == len(availability):
            products = [{"name": name,
                         "link": link,
                         "price": float(price.replace(".", "")[:-7]) + 0.99,
                         "date": datetime.now().strftime("%Y-%m-%d")} for name, price, link, av in
                        zip(products_name, prices, links, availability) if "Casti" in name and "Stoc epuizat" != av]
        else:
            logger.error("Mismatch in lengths of product attributes")

        return products

    def get_cheapest_models(self, products) -> List[dict]:
        """
        Find the three cheapest models of AirPods based on their names
        :param products: list of the products found today
        :return: a list of dictionaries with the cheapest models.
        """
        cheapest_products = [
            {"name": "", "avg_price": 0, "cheapest_price": 5000, "link": ""} for _ in range(3)
        ]
        for product in products:
            if "Max" in product["name"]:
                if product["price"] < cheapest_products[2]["cheapest_price"]:
                    cheapest_products[2]["name"] = product["name"]
                    cheapest_products[2]["cheapest_price"] = product["price"]
                    cheapest_products[2]["link"] = product["link"]
            elif "Pro" in product["name"]:
                if product["price"] < cheapest_products[1]["cheapest_price"]:
                    cheapest_products[1]["name"] = product["name"]
                    cheapest_products[1]["cheapest_price"] = product["price"]
                    cheapest_products[1]["link"] = product["link"]
            elif product["price"] < cheapest_products[0]["cheapest_price"]:
                cheapest_products[0]["name"] = product["name"]
                cheapest_products[0]["cheapest_price"] = product["price"]
                cheapest_products[0]["link"] = product["link"]
        return cheapest_products

    def get_averages(self) -> List:
        """
        Get the price average for every type of product in the last month
        :return: a list containing 3 averages for every airpod model
        """
        file_path = "products.json"
        with open(file_path, "r") as file:
            data = json.load(file)

        airpods_sum = 0
        airpods_num = 0
        airpods_pro_sum = 0
        airpods_pro_num = 0
        airpods_max_sum = 0
        airpods_max_num = 0
        one_month_before = (datetime.now() - relativedelta(months=1)).strftime("%Y-%m-%d")

        for product in reversed(data):
            if product["date"] >= one_month_before:
                if "Pro" in product["name"]:
                    airpods_pro_sum += product["price"]
                    airpods_pro_num += 1
                elif "Max" in product["name"]:
                    airpods_max_sum += product["price"]
                    airpods_max_num += 1
                else:
                    airpods_sum += product["price"]
                    airpods_num += 1

        averages = [0, 0, 0]
        if airpods_num > 0:
            averages[0] = airpods_sum / airpods_num
        if airpods_pro_num > 0:
            averages[1] = airpods_pro_sum / airpods_pro_num
        if airpods_max_num > 0:
            averages[2] = airpods_max_sum / airpods_max_num
        return averages

    def format_message(self, product: dict, discount) -> str:
        product_name = product["name"]
        price = product["cheapest_price"]
        average = product["avg_price"]
        link = product["link"]
        message = (f"An offer has been found for {product_name} at a price of {price:.2f} RON. "
                   f"This price is {discount:.2f}% lower than the average price of the product "
                   f"which is {average} RON. You can find the product on the following link: {link}")
        return message

    def send_offer(self, product: dict, discount):
        smtp_server = "smtp.gmail.com"
        email_user = os.getenv("EMAIL_USER")
        email_password = os.getenv("EMAIL_PASS")
        recipient_email = os.getenv("EMAIL_TO")
        message = self.format_message(product, discount)
        email_subject = f"Product offer for: {product['name']}"
        try:
            with smtplib.SMTP(smtp_server) as connection:
                connection.starttls()
                connection.login(user=email_user, password=email_password)
                connection.sendmail(
                    from_addr=email_user,
                    to_addrs=recipient_email,
                    msg=f"Subject:{email_subject}\n\n{message}"
                )
        except Exception as e:
            logger.error(f"Failed to send offer email: {e}")

    def save_fetched_products(self):
        """
        Holds the entire logic for the project: fetch data from websites,
        call the methods for getting the cheapest models and price averages,
        check if the products found today are on sale and, if so, sends an offer
        :return:None
        """
        file_path = "products.json"
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []

        max_count = 3
        count = 1
        altex_products = []
        while count <= max_count and not altex_products:
            altex_products = self.extract_data_from_altex()
            count += 1
            time.sleep(2)

        count = 1
        flanco_products = []
        while count <= max_count and not flanco_products:
            flanco_products = self.extract_data_from_flanco()
            count += 1
            time.sleep(2)
        products_list = altex_products + flanco_products

        cheapest_products = self.get_cheapest_models(products_list)
        averages = self.get_averages()

        for i in range(3):
            cheapest_products[i]["avg_price"] = averages[i]
        for i in range(3):
            if cheapest_products[i]["cheapest_price"] < averages[i]:
                discount = 100 * (averages[i] - cheapest_products[i]["cheapest_price"]) / averages[i]
                if discount >= 15:
                    self.send_offer(cheapest_products[i], discount)

        if not altex_products:
            logger.error("Still no Altex products after 3 attempts")
        else:
            data.extend(altex_products)

        if not flanco_products:
            logger.error("Still no Flanco products after 3 attempts")
        else:
            data.extend(flanco_products)

        if data:
            with open(file_path, "w") as file:
                json.dump(data, file, indent=4)
        else:
            logger.error("No products found today")
