import akshare
import pandas as pd
import sys
import time
from dataservice.config import CACHE_TTL_SECONDS

# Global cache for stock data
# Key: (stock_code, start_date_formatted, end_date_formatted)
# Value: {'timestamp': float, 'data': pd.DataFrame}
stock_data_cache = {}

def get_stock_history(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """
    Fetches historical stock data using the akshare library, with in-memory caching.

    Args:
        stock_code: The stock symbol (e.g., "600519").
        start_date: The start date for the data (e.g., "2023-01-01" or "20230101").
        end_date: The end date for the data (e.g., "2023-12-31" or "20231231").

    Returns:
        A pandas DataFrame containing the historical stock data, or None if an error occurs
        or no data is found.
    """
    start_date_formatted = start_date.replace("-", "")
    end_date_formatted = end_date.replace("-", "")
    cache_key = (stock_code, start_date_formatted, end_date_formatted)
    current_time = time.time()

    # Check cache first
    if cache_key in stock_data_cache:
        cached_item = stock_data_cache[cache_key]
        if current_time - cached_item['timestamp'] < CACHE_TTL_SECONDS:
            print(f"Returning cached data for {stock_code} from {start_date} to {end_date}.", file=sys.stdout)
            return cached_item['data'].copy() # Return a copy to prevent modification of cached object
        else:
            print(f"Cached data for {stock_code} from {start_date} to {end_date} is expired.", file=sys.stdout)
            del stock_data_cache[cache_key] # Remove expired entry

    print(f"Fetching fresh data for {stock_code} from {start_date} to {end_date}.", file=sys.stdout)
    try:
        stock_df = akshare.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date_formatted,
            end_date=end_date_formatted,
            adjust="qfq"  # Forward-adjusted prices
        )

        if stock_df is None or stock_df.empty:
            print(f"No data found for stock code {stock_code} between {start_date} and {end_date}.", file=sys.stderr)
            # Cache the fact that no data was found to avoid repeated failed calls for a while
            # stock_data_cache[cache_key] = {'timestamp': current_time, 'data': None} # Or an empty DataFrame
            return None

        # Store successfully fetched data in cache
        stock_data_cache[cache_key] = {'timestamp': current_time, 'data': stock_df}
        return stock_df.copy() # Return a copy

    except Exception as e:
        print(f"Error fetching stock data for {stock_code}: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    print("Demonstrating caching functionality for get_stock_history:\n")

    stock_to_test = "000001"
    start_date_test = "20230101"
    end_date_test = "20230115"

    # First call - should fetch from source
    print("First call:")
    data1 = get_stock_history(stock_code=stock_to_test, start_date=start_date_test, end_date=end_date_test)
    if data1 is not None:
        print(f"Data fetched (first call):\n{data1.head()}")
    else:
        print("No data fetched on first call.")

    print("\n" + "="*50 + "\n")

    # Second call - should use cache if within TTL
    print("Second call (should be cached):")
    data2 = get_stock_history(stock_code=stock_to_test, start_date=start_date_test, end_date=end_date_test)
    if data2 is not None:
        print(f"Data fetched (second call):\n{data2.head()}")
    else:
        print("No data fetched on second call.")
    
    # Verify if data is the same (basic check)
    if data1 is not None and data2 is not None and pd.DataFrame.equals(data1, data2):
        print("\nData from first and second call are identical (as expected from cache).")
    elif data1 is None and data2 is None:
        print("\nBoth calls returned no data.")
    else:
        print("\nData from first and second call MISMATCH or one failed!")

    print("\n" + "="*50 + "\n")

    # Test cache expiration (manual adjustment for testing)
    print("Testing cache expiration:")
    # Temporarily reduce TTL for this test case, then restore
    original_ttl = CACHE_TTL_SECONDS
    # Set a very short TTL for testing expiration
    # Directly modifying CACHE_TTL_SECONDS here won't affect the already imported value in the function scope
    # So, we will manually manipulate a cache entry's timestamp for testing
    
    test_stock_expiry = "000002"
    test_start_expiry = "20230201"
    test_end_expiry = "20230205"

    print("Fetching data for expiry test (first call):")
    data_exp1 = get_stock_history(stock_code=test_stock_expiry, start_date=test_start_expiry, end_date=test_end_expiry)
    if data_exp1 is not None:
        print(f"Data fetched for {test_stock_expiry}.")
    
        # Manually expire the cache entry by setting its timestamp way back
        cache_key_exp = (test_stock_expiry, test_start_expiry.replace("-",""), test_end_expiry.replace("-",""))
        if cache_key_exp in stock_data_cache:
            stock_data_cache[cache_key_exp]['timestamp'] = time.time() - CACHE_TTL_SECONDS - 100 # Expired
            print(f"Manually set cache for {test_stock_expiry} to be expired.")
        
        print("\nSecond call for expiry test (should fetch fresh data due to manual expiration):")
        data_exp2 = get_stock_history(stock_code=test_stock_expiry, start_date=test_start_expiry, end_date=test_end_expiry)
        if data_exp2 is not None:
            print(f"Data fetched again for {test_stock_expiry} after manual expiration.")
        else:
            print(f"No data fetched for {test_stock_expiry} on second call after manual expiration.")
    else:
        print(f"Could not fetch initial data for {test_stock_expiry} to test expiration.")


    print("\n" + "="*50 + "\n")
    # Test case: Dates with hyphens (should also be cached correctly)
    print("Test Case: Dates with hyphens (cached)")
    stock_hyphen = "000003" # Using a different stock to avoid conflicts if previous tests ran too close
    start_hyphen = "2023-03-01"
    end_hyphen = "2023-03-05"
    
    print("First call (hyphenated dates):")
    data_h1 = get_stock_history(stock_code=stock_hyphen, start_date=start_hyphen, end_date=end_hyphen)
    if data_h1 is not None:
        print(f"Data fetched for {stock_hyphen} with hyphenated dates.")
    
    print("\nSecond call (hyphenated dates, should be cached):")
    data_h2 = get_stock_history(stock_code=stock_hyphen, start_date=start_hyphen, end_date=end_hyphen)
    if data_h2 is not None:
        print(f"Data fetched for {stock_hyphen} (second call, hyphenated dates).")

    if data_h1 is not None and data_h2 is not None and pd.DataFrame.equals(data_h1, data_h2):
        print(f"\nData for {stock_hyphen} (hyphenated) from first and second call are identical.")
    elif data_h1 is None and data_h2 is None:
         print(f"\nBoth calls for {stock_hyphen} (hyphenated) returned no data.")
    else:
        print(f"\nData for {stock_hyphen} (hyphenated) from first and second call MISMATCH or one failed!")
    
    print("\nEnd of caching demonstration.")
