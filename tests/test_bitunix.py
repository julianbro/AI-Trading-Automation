"""
Tests for Bitunix Exchange Integration.

These tests verify the custom Bitunix API client functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.exchanges import BitunixClient


class TestBitunixClient:
    """Test Bitunix client functionality."""
    
    def test_client_initialization_sandbox(self):
        """Test client initializes in sandbox mode."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.sandbox is True
        assert "testnet" in client.base_url
    
    def test_client_initialization_live(self):
        """Test client initializes in live mode."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=False
        )
        
        assert client.sandbox is False
        assert "testnet" not in client.base_url
    
    def test_symbol_format_conversion(self):
        """Test symbol format conversion (BTC/USDT -> BTCUSDT)."""
        client = BitunixClient(sandbox=True)
        
        # Test in fetch_ticker
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': {
                    'lastPrice': '50000',
                    'bidPrice': '49999',
                    'askPrice': '50001',
                    'highPrice': '51000',
                    'lowPrice': '49000',
                    'volume': '1000'
                }
            }
            
            client.fetch_ticker("BTC/USDT")
            
            # Verify the request was made with formatted symbol
            call_args = mock_request.call_args
            assert call_args[1]['params']['symbol'] == 'BTCUSDT'
    
    def test_fetch_ticker_success(self):
        """Test successful ticker fetch."""
        client = BitunixClient(sandbox=True)
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': {
                    'lastPrice': '50000.5',
                    'bidPrice': '50000.0',
                    'askPrice': '50001.0',
                    'highPrice': '51000.0',
                    'lowPrice': '49000.0',
                    'volume': '1234.5'
                }
            }
            
            result = client.fetch_ticker("BTC/USDT")
            
            assert result['symbol'] == "BTC/USDT"
            assert result['last'] == 50000.5
            assert result['bid'] == 50000.0
            assert result['ask'] == 50001.0
            assert result['high'] == 51000.0
            assert result['low'] == 49000.0
            assert result['volume'] == 1234.5
    
    def test_fetch_ohlcv_success(self):
        """Test successful OHLCV fetch."""
        client = BitunixClient(sandbox=True)
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': [
                    {
                        'time': 1640000000000,
                        'open': '49000',
                        'high': '50000',
                        'low': '48000',
                        'close': '49500',
                        'volume': '100'
                    },
                    {
                        'time': 1640086400000,
                        'open': '49500',
                        'high': '51000',
                        'low': '49000',
                        'close': '50000',
                        'volume': '150'
                    }
                ]
            }
            
            result = client.fetch_ohlcv("BTC/USDT", "1d", 2)
            
            assert len(result) == 2
            assert result[0][0] == 1640000000000  # timestamp
            assert result[0][1] == 49000.0  # open
            assert result[0][2] == 50000.0  # high
            assert result[0][3] == 48000.0  # low
            assert result[0][4] == 49500.0  # close
            assert result[0][5] == 100.0  # volume
    
    def test_timeframe_mapping(self):
        """Test timeframe conversion."""
        client = BitunixClient(sandbox=True)
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {'code': 0, 'data': []}
            
            # Test various timeframes
            timeframe_tests = [
                ('1m', '1'),
                ('5m', '5'),
                ('15m', '15'),
                ('1h', '60'),
                ('4h', '240'),
                ('1d', '1D'),
            ]
            
            for std_tf, expected_tf in timeframe_tests:
                client.fetch_ohlcv("BTC/USDT", std_tf, 10)
                call_args = mock_request.call_args
                assert call_args[1]['params']['interval'] == expected_tf
    
    def test_fetch_balance_sandbox(self):
        """Test balance fetch in sandbox mode."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': [
                    {'asset': 'USDT', 'free': '10000', 'locked': '500'},
                    {'asset': 'BTC', 'free': '0.5', 'locked': '0.1'}
                ]
            }
            
            result = client.fetch_balance()
            
            assert 'USDT' in result
            assert result['USDT']['free'] == 10000.0
            assert result['USDT']['used'] == 500.0
            assert result['USDT']['total'] == 10500.0
    
    def test_create_order_market(self):
        """Test market order creation."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': {
                    'orderId': '12345',
                    'symbol': 'BTCUSDT',
                    'status': 'NEW'
                }
            }
            
            result = client.create_order(
                symbol="BTC/USDT",
                side="BUY",
                order_type="MARKET",
                quantity=0.1
            )
            
            assert result['orderId'] == '12345'
            
            # Verify request parameters
            call_args = mock_request.call_args
            params = call_args[1]['params']
            assert params['symbol'] == 'BTCUSDT'
            assert params['side'] == 'BUY'
            assert params['type'] == 'MARKET'
            assert params['quantity'] == 0.1
    
    def test_create_order_limit(self):
        """Test limit order creation."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        with patch.object(client, '_request') as mock_request:
            mock_request.return_value = {
                'code': 0,
                'data': {
                    'orderId': '12346',
                    'symbol': 'BTCUSDT',
                    'status': 'NEW'
                }
            }
            
            result = client.create_order(
                symbol="BTC/USDT",
                side="SELL",
                order_type="LIMIT",
                quantity=0.1,
                price=51000.0
            )
            
            assert result['orderId'] == '12346'
            
            # Verify price is included for limit orders
            call_args = mock_request.call_args
            params = call_args[1]['params']
            assert params['price'] == 51000.0
    
    def test_api_error_handling(self):
        """Test API error handling."""
        client = BitunixClient(sandbox=True)
        
        with patch.object(client, '_request') as mock_request:
            mock_request.side_effect = Exception("Bitunix API error: Invalid symbol")
            
            with pytest.raises(Exception) as exc_info:
                client.fetch_ticker("INVALID/PAIR")
            
            assert "Invalid symbol" in str(exc_info.value)
    
    def test_signature_generation(self):
        """Test signature generation."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        params = {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'quantity': '0.1'
        }
        
        signature = client._generate_signature(params)
        
        # Verify signature is a hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 produces 64 char hex string
    
    def test_balance_fallback_on_error(self):
        """Test balance returns mock data on API error."""
        client = BitunixClient(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=True
        )
        
        with patch.object(client, '_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            # Should not raise, should return mock balance
            result = client.fetch_balance()
            
            assert 'USDT' in result
            assert result['USDT']['free'] == 10000.0


class TestBitunixIntegrationWithMarketMonitor:
    """Test Bitunix integration with Market Monitor."""
    
    @patch('src.market_monitor.market_monitor.BitunixClient')
    def test_market_monitor_uses_bitunix(self, mock_client_class):
        """Test that Market Monitor correctly initializes Bitunix client."""
        from src.market_monitor import MarketMonitor
        from src.config import config
        
        # Mock config to use bitunix
        with patch.object(config.exchange, 'name', 'bitunix'):
            with patch.object(config.exchange, 'api_key', 'test_key'):
                with patch.object(config.exchange, 'api_secret', 'test_secret'):
                    with patch.object(config.exchange, 'paper_trading', True):
                        
                        # Create mock client instance
                        mock_client_instance = Mock()
                        mock_client_class.return_value = mock_client_instance
                        
                        # Initialize market monitor
                        monitor = MarketMonitor(symbol="BTC/USDT")
                        
                        # Verify BitunixClient was instantiated
                        mock_client_class.assert_called_once()
                        call_kwargs = mock_client_class.call_args[1]
                        assert call_kwargs['api_key'] == 'test_key'
                        assert call_kwargs['api_secret'] == 'test_secret'
                        assert call_kwargs['sandbox'] is True
                        
                        # Verify monitor has the right exchange
                        assert monitor.is_bitunix is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
