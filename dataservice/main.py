from fastapi import FastAPI, HTTPException, Query
from dataservice.crud import get_stock_history
import pandas as pd

app = FastAPI(
    title="Stock Data Service API",
    description="API to fetch historical stock data.",
    version="0.1.0",
)

@app.get("/stock/history/{stock_code}")
async def read_stock_history(
    stock_code: str,
    start_date: str = Query(..., description="Start date for historical data (YYYY-MM-DD or YYYYMMDD)"),
    end_date: str = Query(..., description="End date for historical data (YYYY-MM-DD or YYYYMMDD)")
):
    """
    Retrieve historical stock data for a given stock code and date range.
    """
    # The get_stock_history function is synchronous.
    # FastAPI runs synchronous functions in a separate thread pool,
    # so we don't strictly need to make get_stock_history async for this to work,
    # but for true async operations, get_stock_history would ideally be async.
    stock_data_df = get_stock_history(stock_code=stock_code, start_date=start_date, end_date=end_date)

    if stock_data_df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Stock data not found for symbol '{stock_code}' between {start_date} and {end_date}, or an error occurred."
        )

    if stock_data_df.empty:
        # Although get_stock_history is supposed to return None for empty, we can double check.
        # Or, if get_stock_history could return an empty DataFrame meaning "found stock, but no trades in period"
        # then we might return an empty list. For now, assuming None is the primary indicator of "not found/error".
        # If an empty DataFrame has a different meaning (e.g. valid stock, no data in range),
        # return empty list instead of 404.
        # Based on current crud.py, empty df results in None, so this block might be redundant.
        return []

    # Convert DataFrame to a list of dictionaries (JSON serializable)
    # Dates might need conversion to string if they are datetime objects in the DataFrame
    # akshare usually returns DataFrames with string dates or pandas Timestamps.
    # If they are Timestamps, FastAPI will handle their serialization to ISO 8601 strings.
    # Forcing specific date string format if needed:
    # if '日期' in stock_data_df.columns: # Assuming '日期' is the date column
    #     stock_data_df['日期'] = stock_data_df['日期'].astype(str)

    return stock_data_df.to_dict(orient='records')

# To run this application (for example, using uvicorn):
# uvicorn dataservice.main:app --reload
#
# Example API calls:
# http://127.0.0.1:8000/stock/history/000001?start_date=20230101&end_date=20230110
# http://127.0.0.1:8000/stock/history/000001?start_date=2023-01-01&end_date=2023-01-10
# http://127.0.0.1:8000/docs # For Swagger UI
# http://127.0.0.1:8000/redoc # For ReDoc

if __name__ == "__main__":
    # This section is for local testing and might not be how you'd run it in production.
    # Production typically uses Uvicorn or Hypercorn directly.
    import uvicorn
    print("Starting Uvicorn server for dataservice.main:app on http://127.0.0.1:8000")
    print("Access Swagger UI at http://127.0.0.1:8000/docs")
    print("Access ReDoc at http://127.0.0.1:8000/redoc")
    uvicorn.run(app, host="127.0.0.1", port=8000)
