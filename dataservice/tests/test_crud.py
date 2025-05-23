import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import time
import sys
from io import StringIO # Not strictly needed if we comment out suppression, but good for reference

# Adjust the path to import from the parent directory
# This might be needed if running tests directly from the tests directory
# For a more robust solution, consider structuring as a package and using relative imports
# or setting PYTHONPATH
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataservice.crud import get_stock_history, stock_data_cache
# CACHE_TTL_SECONDS will be patched in the relevant test
from dataservice.config import CACHE_TTL_SECONDS as ACTUAL_CACHE_TTL_SECONDS

# Sample DataFrame to be returned by the mocked akshare function
SAMPLE_COLUMNS = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
SAMPLE_DATA = [
    ('2023-01-01', 10.0, 10.5, 10.8, 9.9, 10000),
    ('2023-01-02', 10.5, 10.2, 10.6, 10.1, 12000),
]
MOCK_DF = pd.DataFrame(SAMPLE_DATA, columns=SAMPLE_COLUMNS)
MOCK_DF_EMPTY = pd.DataFrame([], columns=SAMPLE_COLUMNS)

class TestCrudOperations(unittest.TestCase):

    def setUp(self):
        # Clear cache before each test
        stock_data_cache.clear()
        # Commenting out stdout suppression to see prints from crud.py during tests
        # self.held_stdout = sys.stdout
        # sys.stdout = StringIO()


    def tearDown(self):
        # Restore stdout
        # if hasattr(self, 'held_stdout'): # Ensure it was set
        #    sys.stdout = self.held_stdout
        stock_data_cache.clear()


    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    def test_fetch_success_and_structure(self, mock_akshare_hist: MagicMock):
        """Test successful data fetching and DataFrame structure."""
        mock_akshare_hist.return_value = MOCK_DF.copy()
        
        df = get_stock_history(stock_code="000001", start_date="20230101", end_date="20230102")
        
        mock_akshare_hist.assert_called_once_with(
            symbol="000001",
            period="daily",
            start_date="20230101",
            end_date="20230102",
            adjust="qfq"
        )
        self.assertIsNotNone(df)
        self.assertIsInstance(df, pd.DataFrame)
        pd.testing.assert_frame_equal(df, MOCK_DF)
        self.assertEqual(len(stock_data_cache), 1) # Check if data is cached

    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    def test_caching_works(self, mock_akshare_hist: MagicMock):
        """Test that data is served from cache on subsequent calls."""
        mock_akshare_hist.return_value = MOCK_DF.copy()

        # First call - should call akshare
        df1 = get_stock_history(stock_code="000002", start_date="20230101", end_date="20230102")
        mock_akshare_hist.assert_called_once()
        self.assertIsNotNone(df1)

        # Second call - should use cache
        df2 = get_stock_history(stock_code="000002", start_date="20230101", end_date="20230102")
        mock_akshare_hist.assert_called_once() # Still called only once
        self.assertIsNotNone(df2)
        pd.testing.assert_frame_equal(df1, df2)

    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    @patch('dataservice.crud.time.time')
    @patch('dataservice.crud.CACHE_TTL_SECONDS', 0) # Force immediate expiration for this test
    def test_cache_expiration(self, mock_time_func: MagicMock, mock_akshare_hist: MagicMock): # Patched CACHE_TTL_SECONDS is used by crud.py
        """Test that cache expires and data is fetched again when TTL is 0."""
        mock_akshare_hist.return_value = MOCK_DF.copy()

        first_call_time = 1000.0
        # Ensure second_call_time makes the condition `current_time - cached_timestamp < CACHE_TTL_SECONDS` false.
        # Since CACHE_TTL_SECONDS is 0, condition is `(second_call_time - first_call_time) < 0`.
        # If second_call_time > first_call_time, then (positive_diff < 0) is false, so cache expires.
        second_call_time = 1010.0 

        mock_time_func.side_effect = [
            first_call_time,  # Timestamp for the first call (cache write)
            second_call_time  # Timestamp for the second call (cache check and then re-write)
        ]

        # First call - populates cache
        # crud.py will print "Fetching fresh data for 000003..."
        df1 = get_stock_history(stock_code="000003", start_date="20230101", end_date="20230102")
        
        mock_akshare_hist.assert_called_once()
        self.assertIsNotNone(df1)
        cache_key_exp = ("000003", "20230101", "20230102")
        self.assertIn(cache_key_exp, stock_data_cache)
        self.assertEqual(stock_data_cache[cache_key_exp]['timestamp'], first_call_time) # Check float was stored

        # Second call - should fetch again due to CACHE_TTL_SECONDS = 0
        # crud.py will print "Cached data for 000003 ... is expired."
        # then "Fetching fresh data for 000003..."
        df2 = get_stock_history(stock_code="000003", start_date="20230101", end_date="20230102")
        
        self.assertEqual(mock_akshare_hist.call_count, 2, "akshare.stock_zh_a_hist should be called twice")
        self.assertIsNotNone(df2)
        pd.testing.assert_frame_equal(df1, df2) # Data should be the same as mock is consistent
        # Check that the new timestamp in cache is second_call_time
        self.assertEqual(stock_data_cache[cache_key_exp]['timestamp'], second_call_time)


    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    def test_akshare_error_returns_none(self, mock_akshare_hist: MagicMock):
        """Test that function returns None if akshare raises an exception."""
        mock_akshare_hist.side_effect = Exception("AKShare API Error")
        
        df = get_stock_history(stock_code="000004", start_date="20230101", end_date="20230102")
        
        mock_akshare_hist.assert_called_once()
        self.assertIsNone(df)
        self.assertEqual(len(stock_data_cache), 0) # Nothing should be cached on error

    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    def test_no_data_found_returns_none(self, mock_akshare_hist: MagicMock):
        """Test that function returns None if akshare returns an empty DataFrame."""
        mock_akshare_hist.return_value = MOCK_DF_EMPTY.copy()
        
        df = get_stock_history(stock_code="000005", start_date="20230101", end_date="20230102")
        
        mock_akshare_hist.assert_called_once()
        self.assertIsNone(df)
        self.assertEqual(len(stock_data_cache), 0)


    @patch('dataservice.crud.akshare.stock_zh_a_hist')
    def test_date_formatting_in_akshare_call(self, mock_akshare_hist: MagicMock):
        """Test that dates with hyphens are correctly formatted for akshare call."""
        mock_akshare_hist.return_value = MOCK_DF.copy()
        
        get_stock_history(stock_code="000006", start_date="2023-01-01", end_date="2023-01-02")
        
        mock_akshare_hist.assert_called_once_with(
            symbol="000006",
            period="daily",
            start_date="20230101", # Expecting formatted date
            end_date="20230102",   # Expecting formatted date
            adjust="qfq"
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)
