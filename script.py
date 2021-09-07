# Header
import hashlib
from PIL import Image
import io, os
import requests
import time
import selenium
import pandas as pd
import matplotlib.pyplot as plt 
import seaborn as sns
from selenium import webdriver

DATAROOT = '/Users/ericwang/Documents/'
DRIVER_PATH = DATAROOT + 'chromedriver'
wd = webdriver.Chrome(executable_path=DRIVER_PATH)

# Import, filter, and clean the fields in the tracking sheet to facilitate searching
# Sort by enrollment to prioritize larger schools and re-index the rows
colleges = pd.read_excel(DATAROOT + 'College Logo collection.xlsx', sheet_name = 'Tracking Sheet') 
colleges = colleges.query('Status != "Complete"').sort_values(by='Total Enrollment', ascending=False)
colleges['UnitID'] = colleges['UnitID'].astype(str)

colleges['Institution Name'] = colleges['Institution Name'].str.replace('&', ' and ', regex=True) 
colleges['Search Term'] = colleges['Institution Name'] + ' logo'

colleges.index = range(len(colleges.index))
colleges.head(5)

# Define the scraping function with adjustments: search for images with square aspect ratios,
# repeat a failed scraping with less strict requirements, name files after their ID numbers,
# and track scraping success

def fetch_image_urls(query:str, max_links_to_fetch:int, wd:webdriver, sleep_between_interactions:int=1):
    def scroll_to_end(wd):
        wd.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(sleep_between_interactions)    
    
    # build the google query
    # Augment the query to restrict on square aspect ratios
    search_url = "https://www.google.com/search?safe=off&site=&tbm=isch&source=hp&q={q}&oq={q}&gs_l=img&tbs=iar:s"

    # load the page
    wd.get(search_url.format(q=query))

    image_urls = set()
    image_count = 0
    results_start = 0
    while image_count < max_links_to_fetch:
        scroll_to_end(wd)

        # get all image thumbnail results
        thumbnail_results = wd.find_elements_by_css_selector("img.Q4LuWd")
        number_results = len(thumbnail_results)
        
        print(f"Found: {number_results} search results. Extracting links from {results_start}:{number_results}")
        
        for img in thumbnail_results[results_start:number_results]:
            # try to click every thumbnail such that we can get the real image behind it
            try:
                img.click()
                time.sleep(sleep_between_interactions)
            except Exception:
                continue

            # extract image urls    
            actual_images = wd.find_elements_by_css_selector('img.n3VNCb')
            for actual_image in actual_images:
                if actual_image.get_attribute('src') and 'http' in actual_image.get_attribute('src'):
                    image_urls.add(actual_image.get_attribute('src'))

            image_count = len(image_urls)

            if len(image_urls) >= max_links_to_fetch:
                print(f"Found: {len(image_urls)} image links, done!")
                break
        else:
            print("Found:", len(image_urls), "image links, looking for more ...")
            time.sleep(30)
            return
            load_more_button = wd.find_element_by_css_selector(".mye4qd")
            if load_more_button:
                wd.execute_script("document.querySelector('.mye4qd').click();")

        # move the result startpoint further down
        results_start = len(thumbnail_results)

    return image_urls


def persist_image(folder_path:str,url:str):
    try:
        image_content = requests.get(url).content

    except Exception as e:
        print(f"ERROR - Could not download {url} - {e}")
        global failed_download
        failed_download+=1

    try:
        image_file = io.BytesIO(image_content)
        image = Image.open(image_file).convert('RGB')

        file_path = os.path.join(folder_path, FILENAME + '.jpg')
        
        with open(file_path, 'wb') as f:
            image.save(f, "JPEG", quality=85)
        print(f"SUCCESS - saved {url} - as {file_path}")
        global success
        success+=1
        
    except Exception as e:
        print(f"ERROR - Could not save {url} - {e}")
        global failed_save
        failed_save+=1
                
def search_and_download(search_term:str, driver_path:str, target_path='./images', number_images=5):
    
    # Name the image after the school's ID
    global FILENAME, rerun
    FILENAME = row['UnitID']
        
    target_folder = target_path

    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        
    with webdriver.Chrome(executable_path=driver_path) as wd:
        res = fetch_image_urls(search_term, number_images, wd=wd, sleep_between_interactions=0.5)
                    
    if res is not None:         
        for elem in res:
            persist_image(target_folder,elem)
    
    else:
        print('No suitable images to scrape') 
        global failed_scrape
        failed_scrape+=1

# Commence scraping
success = failed_save = failed_download = failed_scrape = 0
for index, row in colleges.iterrows():
    print(index)
    search_and_download(search_term = row['Search Term'], driver_path = DRIVER_PATH, \
                    target_path = DATAROOT + 'Test', number_images = 1)


# Summarize scraping success rate
dict = {'Success': success, 'Failed to Save': failed_save, 'Failed to Download': failed_download,
       'Failed to Scrape': failed_scrape}

for_plotting = pd.DataFrame(list(dict.items()),columns = ['Type','Frequency']) 
for_plotting['Frequency'] = for_plotting['Frequency'] / for_plotting['Frequency'].sum()

# Create bar chart
colors = ['blue', 'grey', 'grey', 'grey']
ax = sns.barplot(data=for_plotting, x='Type', y='Frequency', palette=colors)
ax.set(ylabel='Relative frequency')
plt.title('Scraping success\n')
plt.show()