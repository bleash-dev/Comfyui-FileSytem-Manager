import asyncio
import urllib.parse
from playwright.async_api import async_playwright, TimeoutError

async def duckduckgo_search(query: str) -> list[str]:
    """
    Performs a search on DuckDuckGo's simple HTML version,
    prints the results for logging, and returns a list of clean, direct URLs.
    
    Returns an empty list if no results are found or an error occurs.
    """
    results_list = []  # 1. Initialize an empty list
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    print(f"[INFO] Performing DDG Search: {search_url}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(search_url, timeout=60000)

            links = await page.locator("a.result__a").all()

            if not links:
                print("[WARNING] No search results found.")
                await browser.close()
                return [] # Return empty list on no results

            print("\n[RESULTS] (Printed from within the function)")
            for i, link_element in enumerate(links[:5]):
                redirect_url = await link_element.get_attribute("href")
                title = await link_element.inner_text()
                
                try:
                    parsed_url = urllib.parse.urlparse(redirect_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    
                    if 'uddg' in query_params:
                        clean_url = query_params['uddg'][0]
                    else:
                        clean_url = redirect_url
                
                except (KeyError, IndexError):
                    clean_url = redirect_url

                print(f"{i+1}. {title}\n   {clean_url}")
                results_list.append(clean_url) # 2. Append the clean URL to the list
            
            await browser.close()
            return results_list # 3. Return the populated list

        except TimeoutError:
            print("[ERROR] Timed out trying to reach DuckDuckGo.")
            return [] # Return empty list on error
        finally:
            # Ensure browser is closed even if an unexpected error occurs
            if 'browser' in locals() and browser.is_connected():
                await browser.close()

# --- 4. UPDATE THE CALLING CODE ---
async def main():
    query = "v1-5-pruned-emaonly-fp16 site:huggingface.co"
    
    # The function now returns the list of URLs, which we store in a variable
    found_urls = await duckduckgo_search(query)

    # Now you can use the list of URLs for other tasks
    if found_urls:
        print("\n-------------------------------------------------")
        print("--- URLs returned by the function and captured: ---")
        print("-------------------------------------------------")
        for url in found_urls:
            print(url)
    else:
        print("\n--- The function returned no URLs. ---")

if __name__ == "__main__":
    asyncio.run(main())