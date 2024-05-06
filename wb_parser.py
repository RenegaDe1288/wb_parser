import json
import requests
from concurrent.futures import ThreadPoolExecutor

from retry import retry
from models import Product, ProductList
from datetime import datetime, date

import logging

console_out = logging.StreamHandler()
logging.basicConfig(handlers=[console_out], level=logging.INFO)


class WBParser:
    CATALOG_URL = 'https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v2.json'

    def __init__(self, url):
        self.url = url

    def __get_catalogs(self) -> dict:
        """Получить все каталоги"""

        return requests.get(self.CATALOG_URL).json()

    def __get_categories(self, catalogs: dict) -> list:
        """Получить все категории"""

        catalog_data = []
        if isinstance(catalogs, dict) and 'childs' not in catalogs:
            catalog_data.append({
                'name': f"{catalogs['name']}",
                'shard': catalogs.get('shard', None),
                'url': catalogs['url'],
                'query': catalogs.get('query', None)
            })
        elif isinstance(catalogs, dict):
            catalog_data.extend(self.__get_categories(catalogs['childs']))
        else:
            for child in catalogs:
                catalog_data.extend(self.__get_categories(child))
        return catalog_data

    def __get_category_by_url(self, catalog_list: list) -> dict:
        """Получить категорию по входному URL"""

        for catalog in catalog_list:
            if catalog['url'] == self.url.split('https://www.wildberries.ru')[-1]:
                logging.info(f'Получаем данные из категории: {catalog["name"]}\n')
                return catalog

    @retry(Exception, tries=-1, delay=0)
    def __scrap_page(self, page: int, shard: str, query: str) -> dict:
        """Собрать данные со страниц"""

        url = f'https://catalog.wb.ru/catalog/{shard}/catalog?appType=1&curr=rub' \
              f'&dest=-1257786' \
              f'&locale=ru' \
              f'&page={page}' \
              f'&sort=popular&spp=0' \
              f'&{query}' \

        r = requests.get(url)
        logging.info(f'Страница {page}')
        return r.json()

    @staticmethod
    def __get_data_from_json(json_data: dict) -> list:
        """Получить данные из JSON"""

        products = []
        for data in json_data['data']['products']:
            products.append(
                Product(
                    title=data.get('name'),
                    price=int(data.get("priceU") / 100),
                    link=f'https://www.wildberries.ru/catalog/{data.get("id")}/detail.aspx'
                )
            )
        return products

    @staticmethod
    def __create_file(data_list: list) -> None:
        """Записать данные в файл"""

        with open("result.json", "w", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    ProductList(products=data_list).model_dump(),
                    indent=4,
                    ensure_ascii=False
                )
            )

    def parse(self) -> None:
        """Запустить парсер"""
        try:
            start = datetime.now().time()
            data_list = []

            with ThreadPoolExecutor(max_workers=8) as executor:
                catalogs = executor.submit(self.__get_catalogs)
                catalog_data = executor.submit(self.__get_categories, catalogs.result())

            category = self.__get_category_by_url(catalog_list=catalog_data.result())

            for page in range(1, 51):

                data = self.__scrap_page(
                    page=page,
                    shard=category['shard'],
                    query=category['query'],
                )

                if len(self.__get_data_from_json(json_data=data)) > 0:
                    data_list.extend(self.__get_data_from_json(json_data=data))
                else:
                    break

            self.__create_file(data_list)

            end = datetime.now().time()
            duration = datetime.combine(date.min, end) - datetime.combine(date.min, start)
            logging.info(f"Затрачено: {duration}")
        except TypeError:
            logging.error(f"Неверно указан URL")


if __name__ == "__main__":
    wb_url = 'https://www.wildberries.ru/catalog/elektronika/detskaya-elektronika'
    WBParser(url=wb_url).parse()
