"""
Тесты для менеджера учетных данных
"""
import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.utils.credentials_manager import (
    CredentialsManager, 
    KeyringCredentialsManager, 
    SSHKeyManager,
    CredentialsError
)


class TestCredentialsManager:
    """Тесты для CredentialsManager"""
    
    @pytest.fixture
    def temp_dir(self):
        """Временная директория для тестов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def credentials_manager(self, temp_dir):
        """Фикстура менеджера учетных данных"""
        return CredentialsManager(config_dir=temp_dir)
    
    def test_credentials_manager_initialization(self, temp_dir):
        """Тест инициализации менеджера"""
        manager = CredentialsManager(config_dir=temp_dir)
        
        assert manager.config_dir == Path(temp_dir)
        assert manager.credentials_file == Path(temp_dir) / "credentials.enc"
        assert manager.key_file == Path(temp_dir) / "key.enc"
    
    def test_generate_encryption_key(self, credentials_manager):
        """Тест генерации ключа шифрования"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            assert credentials_manager.key_file.exists()
            assert hasattr(credentials_manager, 'encryption_key')
    
    def test_encrypt_decrypt_data(self, credentials_manager):
        """Тест шифрования и расшифровки данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            test_data = "test sensitive data"
            encrypted = credentials_manager._encrypt_data(test_data)
            decrypted = credentials_manager._decrypt_data(encrypted)
            
            assert encrypted != test_data
            assert decrypted == test_data
    
    def test_store_credentials(self, credentials_manager):
        """Тест сохранения учетных данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            result = credentials_manager.store_credentials(
                host="test.com",
                username="testuser",
                password="testpass"
            )
            
            assert result is True
            assert credentials_manager.credentials_file.exists()
    
    def test_load_credentials(self, credentials_manager):
        """Тест загрузки учетных данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            # Сохраняем данные
            credentials_manager.store_credentials(
                host="test.com",
                username="testuser",
                password="testpass"
            )
            
            # Загружаем данные
            credentials = credentials_manager.load_credentials("test.com", "testuser")
            
            assert credentials is not None
            assert credentials['host'] == "test.com"
            assert credentials['username'] == "testuser"
            assert credentials['password'] == "testpass"
    
    def test_load_all_credentials(self, credentials_manager):
        """Тест загрузки всех учетных данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            # Сохраняем несколько записей
            credentials_manager.store_credentials("host1.com", "user1", password="pass1")
            credentials_manager.store_credentials("host2.com", "user2", password="pass2")
            
            all_credentials = credentials_manager.load_all_credentials()
            
            assert len(all_credentials) == 2
            assert "user1@host1.com" in all_credentials
            assert "user2@host2.com" in all_credentials
    
    def test_delete_credentials(self, credentials_manager):
        """Тест удаления учетных данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            # Сохраняем данные
            credentials_manager.store_credentials("test.com", "testuser", password="testpass")
            
            # Удаляем данные
            result = credentials_manager.delete_credentials("test.com", "testuser")
            
            assert result is True
            
            # Проверяем, что данные удалены
            credentials = credentials_manager.load_credentials("test.com", "testuser")
            assert credentials is None
    
    def test_list_credentials(self, credentials_manager):
        """Тест получения списка учетных данных"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
            
            # Сохраняем данные
            credentials_manager.store_credentials("host1.com", "user1", password="pass1")
            credentials_manager.store_credentials("host2.com", "user2", password="pass2")
            
            credentials_list = credentials_manager.list_credentials()
            
            assert len(credentials_list) == 2
            assert "user1@host1.com" in credentials_list
            assert "user2@host2.com" in credentials_list
    
    def test_unlock_with_password(self, credentials_manager):
        """Тест разблокировки с паролем"""
        with patch('getpass.getpass', return_value="test_password"):
            credentials_manager._generate_encryption_key()
        
        # Тестируем правильный пароль
        result = credentials_manager.unlock_with_password("test_password")
        assert result is True
        
        # Тестируем неправильный пароль
        result = credentials_manager.unlock_with_password("wrong_password")
        assert result is False
    
    def test_change_master_password(self, credentials_manager):
        """Тест изменения мастер-пароля"""
        with patch('getpass.getpass', return_value="old_password"):
            credentials_manager._generate_encryption_key()
        
        # Сохраняем данные
        credentials_manager.store_credentials("test.com", "testuser", password="testpass")
        
        # Меняем пароль
        result = credentials_manager.change_master_password("old_password", "new_password")
        assert result is True
        
        # Проверяем, что данные все еще доступны с новым паролем
        credentials_manager.unlock_with_password("new_password")
        credentials = credentials_manager.load_credentials("test.com", "testuser")
        assert credentials is not None
        assert credentials['password'] == "testpass"


class TestKeyringCredentialsManager:
    """Тесты для KeyringCredentialsManager"""
    
    @pytest.fixture
    def keyring_manager(self):
        """Фикстура менеджера keyring"""
        return KeyringCredentialsManager()
    
    def test_keyring_manager_initialization(self, keyring_manager):
        """Тест инициализации менеджера keyring"""
        assert keyring_manager.service_name == "ssh_agent"
    
    def test_store_credentials_success(self, keyring_manager):
        """Тест успешного сохранения в keyring"""
        with patch('keyring.set_password') as mock_set:
            mock_set.return_value = None
            
            result = keyring_manager.store_credentials("test.com", "testuser", "testpass")
            
            assert result is True
            mock_set.assert_called_once_with("ssh_agent", "testuser@test.com", "testpass")
    
    def test_store_credentials_failure(self, keyring_manager):
        """Тест неудачного сохранения в keyring"""
        with patch('keyring.set_password') as mock_set:
            mock_set.side_effect = Exception("Keyring error")
            
            result = keyring_manager.store_credentials("test.com", "testuser", "testpass")
            
            assert result is False
    
    def test_load_credentials_success(self, keyring_manager):
        """Тест успешной загрузки из keyring"""
        with patch('keyring.get_password') as mock_get:
            mock_get.return_value = "testpass"
            
            password = keyring_manager.load_credentials("test.com", "testuser")
            
            assert password == "testpass"
            mock_get.assert_called_once_with("ssh_agent", "testuser@test.com")
    
    def test_load_credentials_not_found(self, keyring_manager):
        """Тест загрузки несуществующих данных"""
        with patch('keyring.get_password') as mock_get:
            mock_get.return_value = None
            
            password = keyring_manager.load_credentials("test.com", "testuser")
            
            assert password is None
    
    def test_load_credentials_error(self, keyring_manager):
        """Тест ошибки загрузки из keyring"""
        with patch('keyring.get_password') as mock_get:
            mock_get.side_effect = Exception("Keyring error")
            
            password = keyring_manager.load_credentials("test.com", "testuser")
            
            assert password is None
    
    def test_delete_credentials_success(self, keyring_manager):
        """Тест успешного удаления из keyring"""
        with patch('keyring.delete_password') as mock_delete:
            mock_delete.return_value = None
            
            result = keyring_manager.delete_credentials("test.com", "testuser")
            
            assert result is True
            mock_delete.assert_called_once_with("ssh_agent", "testuser@test.com")
    
    def test_delete_credentials_not_found(self, keyring_manager):
        """Тест удаления несуществующих данных"""
        with patch('keyring.delete_password') as mock_delete:
            from keyring.errors import PasswordDeleteError
            mock_delete.side_effect = PasswordDeleteError("Password not found")
            
            result = keyring_manager.delete_credentials("test.com", "testuser")
            
            assert result is False


class TestSSHKeyManager:
    """Тесты для SSHKeyManager"""
    
    @pytest.fixture
    def temp_ssh_dir(self):
        """Временная директория для SSH ключей"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def key_manager(self, temp_ssh_dir):
        """Фикстура менеджера SSH ключей"""
        return SSHKeyManager(ssh_dir=temp_ssh_dir)
    
    def test_key_manager_initialization(self, temp_ssh_dir):
        """Тест инициализации менеджера ключей"""
        manager = SSHKeyManager(ssh_dir=temp_ssh_dir)
        
        assert manager.ssh_dir == Path(temp_ssh_dir)
    
    def test_find_available_keys_empty(self, key_manager):
        """Тест поиска ключей в пустой директории"""
        keys = key_manager.find_available_keys()
        assert len(keys) == 0
    
    def test_find_available_keys(self, key_manager):
        """Тест поиска доступных ключей"""
        ssh_dir = Path(key_manager.ssh_dir)
        ssh_dir.mkdir(exist_ok=True)
        
        # Создаем тестовые файлы ключей
        key_file = ssh_dir / "id_rsa"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\ntest key content\n-----END PRIVATE KEY-----")
        
        pub_key_file = ssh_dir / "id_rsa.pub"
        pub_key_file.write_text("ssh-rsa test@host")
        
        # Создаем файл, который не является ключом
        other_file = ssh_dir / "config"
        other_file.write_text("Host test")
        
        keys = key_manager.find_available_keys()
        
        assert len(keys) == 1
        assert keys[0] == key_file
    
    def test_validate_key_valid(self, key_manager):
        """Тест валидации валидного ключа"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_key') as temp_file:
            temp_file.write("-----BEGIN PRIVATE KEY-----\ntest key content\n-----END PRIVATE KEY-----")
            temp_file.flush()
            
            with patch('paramiko.RSAKey.from_private_key_file') as mock_rsa:
                mock_rsa.return_value = Mock()
                
                result = key_manager.validate_key(temp_file.name)
                
                assert result is True
                mock_rsa.assert_called_once_with(temp_file.name)
            
            os.unlink(temp_file.name)
    
    def test_validate_key_invalid(self, key_manager):
        """Тест валидации невалидного ключа"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("not a valid key")
            temp_file.flush()
            
            with patch('paramiko.RSAKey.from_private_key_file') as mock_rsa:
                mock_rsa.side_effect = Exception("Invalid key")
                
                result = key_manager.validate_key(temp_file.name)
                
                assert result is False
            
            os.unlink(temp_file.name)
    
    def test_validate_key_not_found(self, key_manager):
        """Тест валидации несуществующего ключа"""
        result = key_manager.validate_key("/nonexistent/path")
        assert result is False
    
    def test_get_key_info(self, key_manager):
        """Тест получения информации о ключе"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_key') as temp_file:
            temp_file.write("-----BEGIN PRIVATE KEY-----\ntest key content\n-----END PRIVATE KEY-----")
            temp_file.flush()
            
            with patch('paramiko.RSAKey.from_private_key_file') as mock_rsa:
                mock_key = Mock()
                mock_key.get_bits.return_value = 2048
                mock_key.get_fingerprint.return_value = b'\x12\x34\x56\x78'
                mock_rsa.return_value = mock_key
                
                info = key_manager.get_key_info(temp_file.name)
                
                assert info is not None
                assert info['type'] == "RSA"
                assert info['size'] == 2048
                assert info['valid'] is True
                assert info['path'] == temp_file.name
            
            os.unlink(temp_file.name)
    
    def test_generate_key_pair_rsa(self, key_manager):
        """Тест генерации RSA пары ключей"""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "test_key"
            
            with patch('paramiko.RSAKey.generate') as mock_generate:
                mock_key = Mock()
                mock_key.write_private_key_file = Mock()
                mock_key.get_name.return_value = "ssh-rsa"
                mock_key.get_base64.return_value = "base64content"
                mock_generate.return_value = mock_key
                
                result = key_manager.generate_key_pair(str(key_path), "rsa", 2048)
                
                assert result is True
                mock_generate.assert_called_once_with(bits=2048)
                mock_key.write_private_key_file.assert_called_once()
    
    def test_generate_key_pair_ed25519(self, key_manager):
        """Тест генерации Ed25519 пары ключей"""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "test_key"
            
            with patch('paramiko.Ed25519Key.generate') as mock_generate:
                mock_key = Mock()
                mock_key.write_private_key_file = Mock()
                mock_key.get_name.return_value = "ssh-ed25519"
                mock_key.get_base64.return_value = "base64content"
                mock_generate.return_value = mock_key
                
                result = key_manager.generate_key_pair(str(key_path), "ed25519")
                
                assert result is True
                mock_generate.assert_called_once()
    
    def test_generate_key_pair_invalid_type(self, key_manager):
        """Тест генерации ключа с неподдерживаемым типом"""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "test_key"
            
            result = key_manager.generate_key_pair(str(key_path), "invalid_type")
            
            assert result is False
