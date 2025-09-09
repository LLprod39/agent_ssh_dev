"""
Менеджер для безопасного хранения и управления учетными данными
"""
import os
import json
import base64
import getpass
from typing import Optional, Dict, Any, List
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring
import keyring.errors

from loguru import logger


class CredentialsError(Exception):
    """Исключение для ошибок работы с учетными данными"""
    pass


class CredentialsManager:
    """Менеджер для безопасного хранения учетных данных"""
    
    def __init__(self, service_name: str = "ssh_agent", config_dir: Optional[str] = None):
        self.service_name = service_name
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".ssh_agent"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Файлы для хранения данных
        self.credentials_file = self.config_dir / "credentials.enc"
        self.key_file = self.config_dir / "key.enc"
        
        self.logger = logger.bind(component="CredentialsManager")
        
        # Инициализация ключа шифрования
        self._ensure_encryption_key()
    
    def _ensure_encryption_key(self):
        """Обеспечивает наличие ключа шифрования"""
        if not self.key_file.exists():
            self._generate_encryption_key()
        
        try:
            with open(self.key_file, 'rb') as f:
                self.encryption_key = f.read()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ключа шифрования: {e}")
            raise CredentialsError("Не удалось загрузить ключ шифрования")
    
    def _generate_encryption_key(self):
        """Генерирует новый ключ шифрования"""
        try:
            # Запрашиваем мастер-пароль у пользователя
            master_password = getpass.getpass("Введите мастер-пароль для шифрования учетных данных: ")
            if not master_password:
                raise CredentialsError("Мастер-пароль не может быть пустым")
            
            # Генерируем соль
            salt = os.urandom(16)
            
            # Создаем ключ из пароля
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            
            # Сохраняем ключ с солью
            encrypted_key = base64.urlsafe_b64encode(salt + key)
            
            with open(self.key_file, 'wb') as f:
                f.write(encrypted_key)
            
            self.encryption_key = key
            self.logger.info("Ключ шифрования создан успешно")
            
        except Exception as e:
            self.logger.error(f"Ошибка создания ключа шифрования: {e}")
            raise CredentialsError("Не удалось создать ключ шифрования")
    
    def _load_encryption_key(self, master_password: str):
        """Загружает ключ шифрования с использованием мастер-пароля"""
        try:
            with open(self.key_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Декодируем данные
            data = base64.urlsafe_b64decode(encrypted_data)
            salt = data[:16]
            stored_key = data[16:]
            
            # Воссоздаем ключ из пароля
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            
            if key != stored_key:
                raise CredentialsError("Неверный мастер-пароль")
            
            self.encryption_key = key
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ключа: {e}")
            return False
    
    def _encrypt_data(self, data: str) -> str:
        """Шифрует данные"""
        try:
            fernet = Fernet(self.encryption_key)
            encrypted_data = fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            self.logger.error(f"Ошибка шифрования данных: {e}")
            raise CredentialsError("Не удалось зашифровать данные")
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Расшифровывает данные"""
        try:
            fernet = Fernet(self.encryption_key)
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Ошибка расшифровки данных: {e}")
            raise CredentialsError("Не удалось расшифровать данные")
    
    def store_credentials(self, host: str, username: str, password: Optional[str] = None, 
                         key_path: Optional[str] = None, **kwargs) -> bool:
        """Сохраняет учетные данные для хоста"""
        try:
            # Загружаем существующие данные
            credentials = self.load_all_credentials()
            
            # Создаем запись для хоста
            host_key = f"{username}@{host}"
            credentials[host_key] = {
                'host': host,
                'username': username,
                'password': password,
                'key_path': key_path,
                'created_at': str(Path().cwd()),  # Временная заглушка
                **kwargs
            }
            
            # Шифруем и сохраняем
            encrypted_data = self._encrypt_data(json.dumps(credentials))
            
            with open(self.credentials_file, 'w') as f:
                f.write(encrypted_data)
            
            self.logger.info(f"Учетные данные сохранены для {host_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения учетных данных: {e}")
            return False
    
    def load_credentials(self, host: str, username: str) -> Optional[Dict[str, Any]]:
        """Загружает учетные данные для хоста"""
        try:
            credentials = self.load_all_credentials()
            host_key = f"{username}@{host}"
            return credentials.get(host_key)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки учетных данных: {e}")
            return None
    
    def load_all_credentials(self) -> Dict[str, Any]:
        """Загружает все учетные данные"""
        if not self.credentials_file.exists():
            return {}
        
        try:
            with open(self.credentials_file, 'r') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._decrypt_data(encrypted_data)
            return json.loads(decrypted_data)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки всех учетных данных: {e}")
            return {}
    
    def delete_credentials(self, host: str, username: str) -> bool:
        """Удаляет учетные данные для хоста"""
        try:
            credentials = self.load_all_credentials()
            host_key = f"{username}@{host}"
            
            if host_key in credentials:
                del credentials[host_key]
                
                # Сохраняем обновленные данные
                encrypted_data = self._encrypt_data(json.dumps(credentials))
                
                with open(self.credentials_file, 'w') as f:
                    f.write(encrypted_data)
                
                self.logger.info(f"Учетные данные удалены для {host_key}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления учетных данных: {e}")
            return False
    
    def list_credentials(self) -> List[str]:
        """Возвращает список сохраненных учетных данных"""
        try:
            credentials = self.load_all_credentials()
            return list(credentials.keys())
        except Exception as e:
            self.logger.error(f"Ошибка получения списка учетных данных: {e}")
            return []
    
    def unlock_with_password(self, master_password: str) -> bool:
        """Разблокирует менеджер с помощью мастер-пароля"""
        return self._load_encryption_key(master_password)
    
    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Изменяет мастер-пароль"""
        try:
            # Проверяем старый пароль
            if not self._load_encryption_key(old_password):
                raise CredentialsError("Неверный старый мастер-пароль")
            
            # Загружаем все данные
            credentials = self.load_all_credentials()
            
            # Генерируем новый ключ
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            new_key = base64.urlsafe_b64encode(kdf.derive(new_password.encode()))
            
            # Сохраняем новый ключ
            encrypted_key = base64.urlsafe_b64encode(salt + new_key)
            with open(self.key_file, 'wb') as f:
                f.write(encrypted_key)
            
            # Обновляем ключ в памяти
            self.encryption_key = new_key
            
            # Пересохраняем данные с новым ключом
            encrypted_data = self._encrypt_data(json.dumps(credentials))
            with open(self.credentials_file, 'w') as f:
                f.write(encrypted_data)
            
            self.logger.info("Мастер-пароль изменен успешно")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка изменения мастер-пароля: {e}")
            return False


class KeyringCredentialsManager:
    """Альтернативный менеджер учетных данных с использованием keyring"""
    
    def __init__(self, service_name: str = "ssh_agent"):
        self.service_name = service_name
        self.logger = logger.bind(component="KeyringCredentialsManager")
    
    def store_credentials(self, host: str, username: str, password: str) -> bool:
        """Сохраняет пароль в системном keyring"""
        try:
            keyring.set_password(self.service_name, f"{username}@{host}", password)
            self.logger.info(f"Пароль сохранен в keyring для {username}@{host}")
            return True
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Ошибка сохранения в keyring: {e}")
            return False
    
    def load_credentials(self, host: str, username: str) -> Optional[str]:
        """Загружает пароль из системного keyring"""
        try:
            password = keyring.get_password(self.service_name, f"{username}@{host}")
            if password:
                self.logger.debug(f"Пароль загружен из keyring для {username}@{host}")
            return password
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Ошибка загрузки из keyring: {e}")
            return None
    
    def delete_credentials(self, host: str, username: str) -> bool:
        """Удаляет пароль из системного keyring"""
        try:
            keyring.delete_password(self.service_name, f"{username}@{host}")
            self.logger.info(f"Пароль удален из keyring для {username}@{host}")
            return True
        except keyring.errors.PasswordDeleteError:
            self.logger.warning(f"Пароль не найден в keyring для {username}@{host}")
            return False
        except keyring.errors.KeyringError as e:
            self.logger.error(f"Ошибка удаления из keyring: {e}")
            return False


class SSHKeyManager:
    """Менеджер для работы с SSH ключами"""
    
    def __init__(self, ssh_dir: Optional[str] = None):
        self.ssh_dir = Path(ssh_dir) if ssh_dir else Path.home() / ".ssh"
        self.logger = logger.bind(component="SSHKeyManager")
    
    def find_available_keys(self) -> List[Path]:
        """Находит доступные SSH ключи"""
        keys = []
        
        if not self.ssh_dir.exists():
            return keys
        
        # Ищем приватные ключи
        for key_file in self.ssh_dir.glob("id_*"):
            if key_file.is_file() and not key_file.name.endswith('.pub'):
                # Проверяем, что это действительно приватный ключ
                try:
                    with open(key_file, 'r') as f:
                        content = f.read()
                        if 'BEGIN' in content and 'PRIVATE KEY' in content:
                            keys.append(key_file)
                except Exception:
                    continue
        
        return keys
    
    def validate_key(self, key_path: str) -> bool:
        """Проверяет валидность SSH ключа"""
        try:
            key_file = Path(key_path).expanduser()
            if not key_file.exists():
                return False
            
            # Пытаемся загрузить ключ с помощью paramiko
            import paramiko
            
            # Проверяем различные типы ключей
            key_types = [
                paramiko.RSAKey,
                paramiko.DSSKey,
                paramiko.ECDSAKey,
                paramiko.Ed25519Key
            ]
            
            for key_type in key_types:
                try:
                    key_type.from_private_key_file(str(key_file))
                    return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка валидации ключа {key_path}: {e}")
            return False
    
    def get_key_info(self, key_path: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о SSH ключе"""
        try:
            key_file = Path(key_path).expanduser()
            if not key_file.exists():
                return None
            
            import paramiko
            
            # Пытаемся определить тип ключа
            key_types = [
                (paramiko.RSAKey, "RSA"),
                (paramiko.DSSKey, "DSS"),
                (paramiko.ECDSAKey, "ECDSA"),
                (paramiko.Ed25519Key, "Ed25519")
            ]
            
            for key_type, key_name in key_types:
                try:
                    key = key_type.from_private_key_file(str(key_file))
                    return {
                        'type': key_name,
                        'size': getattr(key, 'get_bits', lambda: None)(),
                        'fingerprint': key.get_fingerprint().hex(),
                        'path': str(key_file),
                        'valid': True
                    }
                except Exception:
                    continue
            
            return {'valid': False, 'path': str(key_file)}
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о ключе {key_path}: {e}")
            return None
    
    def generate_key_pair(self, key_path: str, key_type: str = "rsa", 
                         key_size: int = 2048, passphrase: Optional[str] = None) -> bool:
        """Генерирует новую пару SSH ключей"""
        try:
            import paramiko
            
            key_path = Path(key_path).expanduser()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Создаем ключ в зависимости от типа
            if key_type.lower() == "rsa":
                key = paramiko.RSAKey.generate(bits=key_size)
            elif key_type.lower() == "ed25519":
                key = paramiko.Ed25519Key.generate()
            elif key_type.lower() == "ecdsa":
                key = paramiko.ECDSAKey.generate()
            else:
                raise ValueError(f"Неподдерживаемый тип ключа: {key_type}")
            
            # Сохраняем приватный ключ
            key.write_private_key_file(str(key_path), password=passphrase)
            
            # Сохраняем публичный ключ
            pub_key_path = key_path.with_suffix(key_path.suffix + '.pub')
            with open(pub_key_path, 'w') as f:
                f.write(f"{key.get_name()} {key.get_base64()} generated@ssh-agent\n")
            
            self.logger.info(f"Пара ключей создана: {key_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации ключей: {e}")
            return False
