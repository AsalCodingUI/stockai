"""Watchlist router — all /watchlist/* endpoints."""

from fastapi import APIRouter, HTTPException

from stockai.data.database import init_database
from stockai.web.schemas import (
    WatchlistDeleteResponse,
    WatchlistItemCreate,
    WatchlistItemListResponse,
    WatchlistItemResponse,
    WatchlistItemUpdate,
)
from stockai.web.services.watchlist import (
    add_to_watchlist,
    get_watchlist_items,
    get_watchlist_item_by_id,
    remove_from_watchlist,
    remove_from_watchlist_by_symbol,
    update_watchlist_item,
    WatchlistItemExistsError,
    WatchlistItemNotFoundError,
)

router = APIRouter(tags=["watchlist"])


@router.get("/watchlist", response_model=WatchlistItemListResponse)
async def list_watchlist() -> dict:
    """Get all watchlist items with associated stock information.

    Returns array of watchlist items with stock details (symbol, name, sector).
    """
    init_database()

    items = get_watchlist_items()

    # Convert to response format
    response_items = [
        WatchlistItemResponse.model_validate(item)
        for item in items
    ]

    return {
        "count": len(response_items),
        "items": response_items,
    }


@router.post("/watchlist", response_model=WatchlistItemResponse, status_code=201)
async def create_watchlist_item(item: WatchlistItemCreate) -> WatchlistItemResponse:
    """Add a stock to the watchlist.

    Accepts stock symbol (or stock_id), optional alert prices, and notes.
    If the stock doesn't exist in the database, it will be created.

    Returns 409 Conflict if the stock is already in the watchlist.
    """
    init_database()

    try:
        watchlist_item = add_to_watchlist(
            stock_id=item.stock_id,
            symbol=item.symbol,
            alert_price_above=item.alert_price_above,
            alert_price_below=item.alert_price_below,
            notes=item.notes,
        )
    except WatchlistItemExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Stock {e.symbol} is already in the watchlist",
        )

    return WatchlistItemResponse.model_validate(watchlist_item)


@router.get("/watchlist/{item_id}", response_model=WatchlistItemResponse)
async def get_watchlist_item(item_id: int) -> WatchlistItemResponse:
    """Get a single watchlist item by its ID.

    Returns the watchlist item with associated stock information (symbol, name, sector).
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    item = get_watchlist_item_by_id(item_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistItemResponse.model_validate(item)


@router.put("/watchlist/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item_endpoint(
    item_id: int,
    update_data: WatchlistItemUpdate,
) -> WatchlistItemResponse:
    """Update a watchlist item's alerts and notes.

    Supports partial updates - only provided fields are updated.
    Set alert prices to 0 to clear them. Set notes to empty string to clear.
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    # Determine what to update vs clear
    # A value of 0 means clear the field, None means don't change
    clear_alert_above = update_data.alert_price_above == 0
    clear_alert_below = update_data.alert_price_below == 0
    clear_notes = update_data.notes == ""

    # Only pass non-zero values for actual updates
    alert_above = (
        update_data.alert_price_above
        if update_data.alert_price_above is not None and update_data.alert_price_above > 0
        else None
    )
    alert_below = (
        update_data.alert_price_below
        if update_data.alert_price_below is not None and update_data.alert_price_below > 0
        else None
    )
    notes = (
        update_data.notes
        if update_data.notes is not None and update_data.notes != ""
        else None
    )

    try:
        item = update_watchlist_item(
            item_id=item_id,
            alert_price_above=alert_above,
            alert_price_below=alert_below,
            notes=notes,
            clear_alert_above=clear_alert_above,
            clear_alert_below=clear_alert_below,
            clear_notes=clear_notes,
        )
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistItemResponse.model_validate(item)


@router.delete("/watchlist/{item_id}", response_model=WatchlistDeleteResponse)
async def delete_watchlist_item(item_id: int) -> WatchlistDeleteResponse:
    """Remove a stock from the watchlist by watchlist item ID.

    Returns the deleted watchlist item information for confirmation.
    Returns 404 if the watchlist item is not found.
    """
    init_database()

    try:
        deleted_item = remove_from_watchlist(item_id)
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist item with id={item_id} not found",
        )

    return WatchlistDeleteResponse(
        message=f"Successfully removed {deleted_item.stock.symbol} from watchlist",
        deleted_item=WatchlistItemResponse.model_validate(deleted_item),
    )


@router.delete("/watchlist/symbol/{symbol}", response_model=WatchlistDeleteResponse)
async def delete_watchlist_item_by_symbol(symbol: str) -> WatchlistDeleteResponse:
    """Remove a stock from the watchlist by stock symbol.

    Convenience endpoint that allows removing a stock from the watchlist
    using the stock symbol instead of the watchlist item ID.
    Returns 404 if the stock is not in the watchlist.
    """
    init_database()

    try:
        deleted_item = remove_from_watchlist_by_symbol(symbol)
    except WatchlistItemNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {symbol.upper()} is not in the watchlist",
        )

    return WatchlistDeleteResponse(
        message=f"Successfully removed {deleted_item.stock.symbol} from watchlist",
        deleted_item=WatchlistItemResponse.model_validate(deleted_item),
    )
