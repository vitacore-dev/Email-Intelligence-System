from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class BrowserSearchService:
    """Сервис для поиска через браузер с использованием Selenium"""
    
    def __init__(self, headless: bool = True):
        """
        Инициализация веб-драйвера Chrome
        
        Args:
            headless: Запуск в скрытом режиме (без GUI)
        """
        self.driver = None
        self.headless = headless
        self.search_delay_range = (2, 5)  # Случайная задержка между поисками
        self._init_driver()
    
    def _init_driver(self):
        """Инициализация веб-драйвера с настройками"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Настройки для обхода блокировок
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Установка User-Agent для имитации реального браузера
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Установка размера окна
            chrome_options.add_argument("--window-size=1920,1080")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Выполнение JavaScript для скрытия признаков автоматизации
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Веб-драйвер Chrome успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации веб-драйвера: {str(e)}")
            raise
    
    def search_google(self, query: str, max_results: int = 15) -> List[Dict[str, str]]:
        """
        Выполняет поиск в Google и возвращает результаты
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            
        Returns:
            Список результатов поиска
        """
        if not self.driver:
            logger.error("Веб-драйвер не инициализирован")
            return []
        
        try:
            logger.info(f"Выполняем поиск в Google: {query}")
            
            # Переходим на Google
            self.driver.get("https://www.google.com")
            
            # Случайная задержка для имитации человеческого поведения
            time.sleep(random.uniform(1, 3))
            
            # Обработка соглашения с cookies (если появляется)
            try:
                accept_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Принять')]"))
                )
                accept_button.click()
                time.sleep(1)
            except TimeoutException:
                pass  # Соглашение не появилось
            
            # Находим поле поиска
            search_selectors = [
                "input[name='q']",
                "input[title='Search']", 
                "textarea[name='q']"
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not search_box:
                logger.error("Не удалось найти поле поиска на странице Google")
                return []
            
            # Очищаем поле и вводим запрос
            search_box.clear()
            
            # Имитируем человеческий ввод с задержками
            for char in query:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            # Нажимаем Enter
            search_box.send_keys(Keys.RETURN)
            
            # Ждем загрузки результатов
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.g, div[data-ved]"))
            )
            
            # Случайная задержка после загрузки
            time.sleep(random.uniform(2, 4))
            
            return self._extract_search_results(max_results)
            
        except TimeoutException:
            logger.error(f"Тайм-аут при поиске запроса: {query}")
            return []
        except WebDriverException as e:
            logger.error(f"Ошибка WebDriver при поиске: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске: {str(e)}")
            return []
    
    def _extract_search_results(self, max_results: int) -> List[Dict[str, str]]:
        """Извлекает результаты поиска со страницы"""
        results = []
        
        try:
            # Различные селекторы для результатов поиска
            result_selectors = [
                "div.g",
                "div[data-ved] h3 ..",
                ".yuRUbf",
                ".tF2Cxc"
            ]
            
            search_results = []
            for selector in result_selectors:
                try:
                    search_results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if search_results:
                        break
                except:
                    continue
            
            if not search_results:
                logger.warning("Не удалось найти результаты поиска на странице")
                return []
            
            logger.info(f"Найдено {len(search_results)} потенциальных результатов")
            
            for result_element in search_results[:max_results * 2]:  # Берем больше, чем нужно, на случай ошибок
                try:
                    result_data = self._extract_single_result(result_element)
                    if result_data and result_data['title'] and result_data['link']:
                        results.append(result_data)
                        
                        if len(results) >= max_results:
                            break
                            
                except Exception as e:
                    logger.debug(f"Ошибка извлечения результата: {str(e)}")
                    continue
            
            logger.info(f"Успешно извлечено {len(results)} результатов поиска")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении результатов: {str(e)}")
            return results
    
    def _extract_single_result(self, result_element) -> Optional[Dict[str, str]]:
        """Извлекает данные из одного результата поиска"""
        try:
            # Попытка найти заголовок
            title = ""
            title_selectors = ["h3", ".LC20lb", ".DKV0Md"]
            for selector in title_selectors:
                try:
                    title_element = result_element.find_element(By.CSS_SELECTOR, selector)
                    title = title_element.text.strip()
                    if title:
                        break
                except NoSuchElementException:
                    continue
            
            # Попытка найти ссылку
            link = ""
            link_selectors = ["a", "h3 a", ".yuRUbf a"]
            for selector in link_selectors:
                try:
                    link_element = result_element.find_element(By.CSS_SELECTOR, selector)
                    link = link_element.get_attribute("href")
                    if link and link.startswith("http"):
                        break
                except NoSuchElementException:
                    continue
            
            # Попытка найти описание
            snippet = ""
            snippet_selectors = [".VwiC3b", ".IsZvec", ".s3v9rd", ".BNeawe.s3v9rd"]
            for selector in snippet_selectors:
                try:
                    snippet_element = result_element.find_element(By.CSS_SELECTOR, selector)
                    snippet = snippet_element.text.strip()
                    if snippet:
                        break
                except NoSuchElementException:
                    continue
            
            # Проверяем, что у нас есть минимально необходимые данные
            if not title and not link:
                return None
            
            return {
                'title': title or "No title",
                'link': link or "",
                'snippet': snippet or "No description",
                'source': 'browser_search'
            }
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения отдельного результата: {str(e)}")
            return None
    
    def search_multiple_queries(self, queries: List[str], max_results_per_query: int = 15) -> List[Dict[str, str]]:
        """
        Выполняет поиск по нескольким запросам
        
        Args:
            queries: Список поисковых запросов
            max_results_per_query: Максимальное количество результатов на запрос
            
        Returns:
            Объединенный список результатов
        """
        all_results = []
        
        for i, query in enumerate(queries):
            try:
                logger.info(f"Выполняем запрос {i+1}/{len(queries)}: {query}")
                
                results = self.search_google(query, max_results_per_query)
                all_results.extend(results)
                
                # Случайная задержка между запросами
                if i < len(queries) - 1:  # Не ждем после последнего запроса
                    delay = random.uniform(*self.search_delay_range)
                    logger.info(f"Ожидание {delay:.1f} секунд перед следующим запросом...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Ошибка при выполнении запроса '{query}': {str(e)}")
                continue
        
        # Удаляем дубликаты по URL
        seen_links = set()
        unique_results = []
        
        for result in all_results:
            link = result.get('link', '')
            if link and link not in seen_links:
                seen_links.add(link)
                unique_results.append(result)
        
        logger.info(f"Итого уникальных результатов: {len(unique_results)}")
        return unique_results
    
    def close(self):
        """Закрывает браузер и освобождает ресурсы"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Веб-драйвер успешно закрыт")
            except Exception as e:
                logger.error(f"Ошибка при закрытии веб-драйвера: {str(e)}")
            finally:
                self.driver = None
    
    def __del__(self):
        """Деструктор для автоматического закрытия драйвера"""
        self.close()
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка context manager"""
        self.close()


# Функция для тестирования
def test_browser_search():
    """Тестовая функция для проверки работы браузерного поиска"""
    
    with BrowserSearchService(headless=False) as search_service:  # headless=False для отладки
        test_queries = [
            '"test@example.com"',
            '"test@example.com" author',
            '"test@example.com" research'
        ]
        
        results = search_service.search_multiple_queries(test_queries, max_results_per_query=5)
        
        print(f"Найдено {len(results)} результатов:")
        for i, result in enumerate(results[:10], 1):
            print(f"\n{i}. {result['title']}")
            print(f"   URL: {result['link']}")
            print(f"   Описание: {result['snippet'][:100]}...")


if __name__ == "__main__":
    test_browser_search()
