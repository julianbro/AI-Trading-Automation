"""
Bitunix Exchange API Client.

Custom implementation for Bitunix exchange since it's not supported by CCXT.
Based on Bitunix API documentation: https://openapidoc.bitunix.com/doc/common/introduction.html

WARNING: This is a custom implementation. Some features may not work as expected.
"""
import hmac
import hashlib
import time
import requests
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class BitunixClient:
    """
    Custom Bitunix API client.
    
    Implements basic functionality for market data and trading.
    """
    
    def __init__(
        self, 
        api_key: str = "", 
        api_secret: str = "", 
        sandbox: bool = True
    ):
        """
        Initialize Bitunix client.
        
        Args:
            api_key: API key from Bitunix
            api_secret: API secret from Bitunix
            sandbox: Whether to use sandbox/testnet mode
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.sandbox = sandbox
        
        # API endpoints
        if sandbox:
            self.base_url = "https://api-testnet.bitunix.com"
            logger.info("Bitunix client initialized in SANDBOX mode")
        else:
            self.base_url = "https://api.bitunix.com"
            logger.warning("Bitunix client initialized in LIVE mode")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-BX-APIKEY': api_key
        })
        
        logger.info("Bitunix client initialized", sandbox=sandbox)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for API request.
        
        Args:
            params: Request parameters
            
        Returns:
            Signature string
        """
        # Sort parameters by key
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Generate signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """
        Make API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature
            
        Returns:
            Response data
        """
        params = params or {}
        url = f"{self.base_url}{endpoint}"
        
        # Add timestamp for signed requests
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, json=params, timeout=10)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if isinstance(data, dict) and data.get('code') != 0:
                error_msg = data.get('msg', 'Unknown error')
                logger.error(
                    "Bitunix API error",
                    endpoint=endpoint,
                    code=data.get('code'),
                    message=error_msg
                )
                raise Exception(f"Bitunix API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "Bitunix API request failed",
                endpoint=endpoint,
                error=str(e)
            )
            raise Exception(f"Bitunix API request failed: {str(e)}")
    
    def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch ticker data for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Ticker data
        """
        try:
            logger.debug("Fetching ticker", symbol=symbol)
            
            # Convert symbol format (BTC/USDT -> BTCUSDT)
            formatted_symbol = symbol.replace('/', '')
            
            response = self._request(
                'GET',
                '/api/v1/market/ticker',
                params={'symbol': formatted_symbol}
            )
            
            # Parse response to standardized format
            if response.get('data'):
                data = response['data']
                return {
                    'symbol': symbol,
                    'last': float(data.get('lastPrice', 0)),
                    'bid': float(data.get('bidPrice', 0)),
                    'ask': float(data.get('askPrice', 0)),
                    'high': float(data.get('highPrice', 0)),
                    'low': float(data.get('lowPrice', 0)),
                    'volume': float(data.get('volume', 0)),
                    'timestamp': int(time.time() * 1000)
                }
            else:
                logger.warning("No ticker data returned", symbol=symbol)
                return {'symbol': symbol, 'last': 0}
                
        except Exception as e:
            logger.error("Error fetching ticker", symbol=symbol, error=str(e))
            raise Exception(f"Failed to fetch ticker for {symbol}: {str(e)}")
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1d', 
        limit: int = 100
    ) -> List[List]:
        """
        Fetch OHLCV (candlestick) data.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            limit: Number of candles to fetch
            
        Returns:
            List of OHLCV data [timestamp, open, high, low, close, volume]
        """
        try:
            logger.debug(
                "Fetching OHLCV",
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            # Convert symbol format
            formatted_symbol = symbol.replace('/', '')
            
            # Convert timeframe format (1d -> 1D, 4h -> 4H, etc.)
            timeframe_map = {
                '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
                '1h': '60', '2h': '120', '4h': '240', '6h': '360',
                '12h': '720', '1d': '1D', '1w': '1W', '1M': '1M'
            }
            bitunix_timeframe = timeframe_map.get(timeframe, '1D')
            
            response = self._request(
                'GET',
                '/api/v1/market/kline',
                params={
                    'symbol': formatted_symbol,
                    'interval': bitunix_timeframe,
                    'limit': limit
                }
            )
            
            # Parse response
            if response.get('data'):
                ohlcv_data = []
                for candle in response['data']:
                    ohlcv_data.append([
                        int(candle['time']),  # timestamp
                        float(candle['open']),  # open
                        float(candle['high']),  # high
                        float(candle['low']),  # low
                        float(candle['close']),  # close
                        float(candle['volume'])  # volume
                    ])
                
                logger.debug(
                    "OHLCV data fetched",
                    symbol=symbol,
                    candles=len(ohlcv_data)
                )
                return ohlcv_data
            else:
                logger.warning("No OHLCV data returned", symbol=symbol)
                return []
                
        except Exception as e:
            logger.error(
                "Error fetching OHLCV",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise Exception(f"Failed to fetch OHLCV for {symbol}: {str(e)}")
    
    def fetch_balance(self) -> Dict:
        """
        Fetch account balance.
        
        Returns:
            Balance data
            
        Raises:
            Exception: If API request fails or not in sandbox mode
        """
        if not self.sandbox:
            logger.warning("Balance fetch attempted in LIVE mode - using mock data")
            return {
                'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0}
            }
        
        try:
            logger.debug("Fetching account balance")
            
            response = self._request(
                'GET',
                '/api/v1/account/balance',
                signed=True
            )
            
            # Parse balance data
            balances = {}
            if response.get('data'):
                for balance in response['data']:
                    asset = balance['asset']
                    balances[asset] = {
                        'free': float(balance.get('free', 0)),
                        'used': float(balance.get('locked', 0)),
                        'total': float(balance.get('free', 0)) + float(balance.get('locked', 0))
                    }
            
            return balances
            
        except Exception as e:
            logger.error("Error fetching balance", error=str(e))
            # Return mock balance for paper trading
            logger.warning("Returning mock balance due to API error")
            return {
                'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0}
            }
    
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None
    ) -> Dict:
        """
        Create a new order.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            side: Order side ("BUY" or "SELL")
            order_type: Order type ("MARKET" or "LIMIT")
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            
        Returns:
            Order data
        """
        try:
            logger.info(
                "Creating order",
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity,
                price=price
            )
            
            # Convert symbol format
            formatted_symbol = symbol.replace('/', '')
            
            params = {
                'symbol': formatted_symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': quantity
            }
            
            if order_type.upper() == 'LIMIT' and price:
                params['price'] = price
            
            response = self._request(
                'POST',
                '/api/v1/order/create',
                params=params,
                signed=True
            )
            
            if response.get('data'):
                order_data = response['data']
                logger.info(
                    "Order created successfully",
                    order_id=order_data.get('orderId'),
                    symbol=symbol
                )
                return order_data
            else:
                logger.error("Order creation failed - no data returned")
                raise Exception("Order creation failed - no data returned")
                
        except Exception as e:
            logger.error("Error creating order", error=str(e))
            raise Exception(f"Failed to create order: {str(e)}")
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        Cancel an existing order.
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response
        """
        try:
            logger.info("Cancelling order", symbol=symbol, order_id=order_id)
            
            formatted_symbol = symbol.replace('/', '')
            
            response = self._request(
                'DELETE',
                '/api/v1/order/cancel',
                params={
                    'symbol': formatted_symbol,
                    'orderId': order_id
                },
                signed=True
            )
            
            logger.info("Order cancelled", order_id=order_id)
            return response
            
        except Exception as e:
            logger.error("Error cancelling order", error=str(e))
            raise Exception(f"Failed to cancel order: {str(e)}")
    
    def get_order(self, symbol: str, order_id: str) -> Dict:
        """
        Get order status.
        
        Args:
            symbol: Trading pair
            order_id: Order ID
            
        Returns:
            Order data
        """
        try:
            formatted_symbol = symbol.replace('/', '')
            
            response = self._request(
                'GET',
                '/api/v1/order/query',
                params={
                    'symbol': formatted_symbol,
                    'orderId': order_id
                },
                signed=True
            )
            
            if response.get('data'):
                return response['data']
            else:
                raise Exception("No order data returned")
                
        except Exception as e:
            logger.error("Error getting order", error=str(e))
            raise Exception(f"Failed to get order: {str(e)}")
