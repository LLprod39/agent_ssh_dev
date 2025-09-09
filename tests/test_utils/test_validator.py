"""
Тесты для Validator
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.utils.validator import (
    ValidationError, ConfigValidator, CommandValidator, ServerInfoValidator,
    FileValidator, DataValidator, validate_config_file
)


class TestValidationError:
    """Тесты для ValidationError"""
    
    def test_validation_error_creation(self):
        """Тест создания исключения валидации"""
        error = ValidationError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestConfigValidator:
    """Тесты для ConfigValidator"""
    
    def test_validate_yaml_file_success(self):
        """Тест успешной валидации YAML файла"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
            test:
              key1: value1
              key2: value2
            """)
            f.flush()
            
            result = ConfigValidator.validate_yaml_file(f.name)
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_yaml_file_invalid_yaml(self):
        """Тест валидации невалидного YAML файла"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
            test:
              key1: value1
              key2: [unclosed list
            """)
            f.flush()
            
            with pytest.raises(ValidationError) as exc_info:
                ConfigValidator.validate_yaml_file(f.name)
            
            assert "Ошибка парсинга YAML файла" in str(exc_info.value)
            
            os.unlink(f.name)
    
    def test_validate_yaml_file_not_found(self):
        """Тест валидации несуществующего файла"""
        with pytest.raises(ValidationError) as exc_info:
            ConfigValidator.validate_yaml_file("nonexistent.yaml")
        
        assert "Файл не найден" in str(exc_info.value)
    
    def test_validate_config_structure_success(self):
        """Тест успешной валидации структуры конфигурации"""
        config = {
            "section1": {"key1": "value1"},
            "section2": {"key2": "value2"},
            "section3": {"key3": "value3"}
        }
        required_sections = ["section1", "section2", "section3"]
        
        result = ConfigValidator.validate_config_structure(config, required_sections)
        assert result is True
    
    def test_validate_config_structure_missing_sections(self):
        """Тест валидации структуры с отсутствующими секциями"""
        config = {
            "section1": {"key1": "value1"},
            "section2": {"key2": "value2"}
        }
        required_sections = ["section1", "section2", "section3", "section4"]
        
        with pytest.raises(ValidationError) as exc_info:
            ConfigValidator.validate_config_structure(config, required_sections)
        
        assert "Отсутствуют обязательные секции" in str(exc_info.value)
        assert "section3" in str(exc_info.value)
        assert "section4" in str(exc_info.value)


class TestCommandValidator:
    """Тесты для CommandValidator"""
    
    def test_initialization_default(self):
        """Тест инициализации с настройками по умолчанию"""
        validator = CommandValidator()
        
        assert len(validator.forbidden_commands) > 0
        assert validator.allowed_commands is None
        assert len(validator.dangerous_patterns) > 0
        assert validator.validate_commands is True
        assert validator.log_forbidden_attempts is True
        assert validator.require_confirmation_for_dangerous is True
        assert validator.allowed_commands_only is False
        assert validator.validation_stats['total_validations'] == 0
    
    def test_initialization_custom(self):
        """Тест инициализации с пользовательскими настройками"""
        forbidden = ["rm -rf /", "dd if=/dev/zero"]
        allowed = ["ls", "cat", "grep"]
        security_config = {
            'validate_commands': False,
            'log_forbidden_attempts': False,
            'require_confirmation_for_dangerous': False,
            'allowed_commands_only': True
        }
        
        validator = CommandValidator(
            forbidden_commands=forbidden,
            allowed_commands=allowed,
            security_config=security_config
        )
        
        assert validator.forbidden_commands == forbidden
        assert validator.allowed_commands == allowed
        assert validator.validate_commands is False
        assert validator.log_forbidden_attempts is False
        assert validator.require_confirmation_for_dangerous is False
        assert validator.allowed_commands_only is True
    
    def test_validate_command_empty(self):
        """Тест валидации пустой команды"""
        validator = CommandValidator()
        
        result = validator.validate_command("")
        
        assert result['valid'] is False
        assert "Команда не может быть пустой" in result['errors']
        assert result['security_level'] == 'safe'
        assert validator.validation_stats['rejected_commands'] == 1
    
    def test_validate_command_whitespace_only(self):
        """Тест валидации команды только с пробелами"""
        validator = CommandValidator()
        
        result = validator.validate_command("   ")
        
        assert result['valid'] is False
        assert "Команда не может быть пустой" in result['errors']
    
    def test_validate_command_forbidden(self):
        """Тест валидации запрещенной команды"""
        validator = CommandValidator()
        
        result = validator.validate_command("rm -rf /")
        
        assert result['valid'] is False
        assert "Команда запрещена" in result['errors'][0]
        assert result['security_level'] == 'forbidden'
        assert validator.validation_stats['forbidden_attempts'] == 1
        assert validator.validation_stats['rejected_commands'] == 1
    
    def test_validate_command_allowed_list_mode(self):
        """Тест валидации в режиме белого списка"""
        allowed = ["ls", "cat", "grep", "sudo apt"]
        validator = CommandValidator(
            allowed_commands=allowed,
            security_config={'allowed_commands_only': True}
        )
        
        # Разрешенная команда
        result = validator.validate_command("ls -la")
        assert result['valid'] is True
        assert result['security_level'] == 'safe'
        
        # Запрещенная команда
        result = validator.validate_command("rm -rf /")
        assert result['valid'] is False
        assert "не входит в список разрешенных" in result['errors'][0]
    
    def test_validate_command_dangerous_pattern(self):
        """Тест валидации команды с опасным паттерном"""
        validator = CommandValidator()
        
        result = validator.validate_command("dd if=/dev/zero of=/dev/sda")
        
        assert result['valid'] is True  # Команда не запрещена полностью
        assert len(result['warnings']) > 0
        assert result['security_level'] == 'dangerous'
        assert result['requires_confirmation'] is True
        assert validator.validation_stats['dangerous_patterns_detected'] == 1
    
    def test_validate_command_safe(self):
        """Тест валидации безопасной команды"""
        validator = CommandValidator()
        
        result = validator.validate_command("ls -la /home")
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert len(result['warnings']) == 0
        assert result['security_level'] == 'safe'
        assert result['requires_confirmation'] is False
        assert validator.validation_stats['allowed_commands'] == 1
    
    def test_is_command_allowed(self):
        """Тест проверки разрешенной команды"""
        allowed = ["ls", "cat", "grep"]
        validator = CommandValidator(allowed_commands=allowed)
        
        assert validator._is_command_allowed("ls -la") is True
        assert validator._is_command_allowed("cat file.txt") is True
        assert validator._is_command_allowed("rm -rf /") is False
    
    def test_is_command_forbidden(self):
        """Тест проверки запрещенной команды"""
        validator = CommandValidator()
        
        assert validator._is_command_forbidden("rm -rf /") is True
        assert validator._is_command_forbidden("ls -la") is False
        assert validator._is_command_forbidden("dd if=/dev/zero") is True
    
    def test_check_dangerous_patterns_advanced(self):
        """Тест расширенной проверки опасных паттернов"""
        validator = CommandValidator()
        
        warnings = validator._check_dangerous_patterns_advanced("dd if=/dev/zero of=/dev/sda")
        assert len(warnings) > 0
        assert "dd\\s+if=/dev/(zero|random|urandom)" in warnings[0]
        
        warnings = validator._check_dangerous_patterns_advanced("ls -la")
        assert len(warnings) == 0
    
    def test_get_validation_stats(self):
        """Тест получения статистики валидации"""
        validator = CommandValidator()
        
        # Выполняем несколько валидаций
        validator.validate_command("ls -la")  # Успешная
        validator.validate_command("rm -rf /")  # Запрещенная
        validator.validate_command("dd if=/dev/zero")  # Опасная
        
        stats = validator.get_validation_stats()
        
        assert stats['total_validations'] == 3
        assert stats['forbidden_attempts'] == 1
        assert stats['dangerous_patterns_detected'] == 1
        assert stats['allowed_commands'] == 1
        assert stats['rejected_commands'] == 1
        assert stats['success_rate'] == 33.33  # 1/3 * 100
    
    def test_reset_stats(self):
        """Тест сброса статистики"""
        validator = CommandValidator()
        
        # Добавляем некоторую статистику
        validator.validate_command("ls -la")
        validator.validate_command("rm -rf /")
        
        assert validator.validation_stats['total_validations'] == 2
        
        # Сбрасываем статистику
        validator.reset_stats()
        
        assert validator.validation_stats['total_validations'] == 0
        assert validator.validation_stats['forbidden_attempts'] == 0
        assert validator.validation_stats['allowed_commands'] == 0
    
    def test_add_forbidden_command(self):
        """Тест добавления запрещенной команды"""
        validator = CommandValidator()
        initial_count = len(validator.forbidden_commands)
        
        validator.add_forbidden_command("new_dangerous_command")
        
        assert len(validator.forbidden_commands) == initial_count + 1
        assert "new_dangerous_command" in validator.forbidden_commands
        
        # Проверяем что команда теперь запрещена
        result = validator.validate_command("new_dangerous_command")
        assert result['valid'] is False
    
    def test_remove_forbidden_command(self):
        """Тест удаления запрещенной команды"""
        validator = CommandValidator()
        initial_count = len(validator.forbidden_commands)
        
        # Добавляем команду
        validator.add_forbidden_command("test_command")
        assert len(validator.forbidden_commands) == initial_count + 1
        
        # Удаляем команду
        validator.remove_forbidden_command("test_command")
        assert len(validator.forbidden_commands) == initial_count
        assert "test_command" not in validator.forbidden_commands
    
    def test_add_dangerous_pattern(self):
        """Тест добавления опасного паттерна"""
        validator = CommandValidator()
        initial_count = len(validator.dangerous_patterns)
        
        validator.add_dangerous_pattern(r"test_pattern")
        
        assert len(validator.dangerous_patterns) == initial_count + 1
        assert r"test_pattern" in validator.dangerous_patterns
    
    def test_is_command_safe(self):
        """Тест быстрой проверки безопасности команды"""
        validator = CommandValidator()
        
        assert validator.is_command_safe("ls -la") is True
        assert validator.is_command_safe("rm -rf /") is False
        assert validator.is_command_safe("dd if=/dev/zero") is False  # Опасная команда


class TestServerInfoValidator:
    """Тесты для ServerInfoValidator"""
    
    def test_validate_host_ip_address(self):
        """Тест валидации IP адреса"""
        # Валидные IP адреса
        assert ServerInfoValidator.validate_host("192.168.1.1") is True
        assert ServerInfoValidator.validate_host("10.0.0.1") is True
        assert ServerInfoValidator.validate_host("127.0.0.1") is True
        
        # Невалидные IP адреса
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("256.1.1.1")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("192.168.1.256")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("192.168.1")
    
    def test_validate_host_domain_name(self):
        """Тест валидации доменного имени"""
        # Валидные доменные имена
        assert ServerInfoValidator.validate_host("example.com") is True
        assert ServerInfoValidator.validate_host("sub.example.com") is True
        assert ServerInfoValidator.validate_host("test-server.example.org") is True
        
        # Невалидные доменные имена
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("-example.com")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("example-.com")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("example..com")
    
    def test_validate_host_empty(self):
        """Тест валидации пустого хоста"""
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_host("   ")
    
    def test_validate_port_valid(self):
        """Тест валидации валидных портов"""
        assert ServerInfoValidator.validate_port(22) is True
        assert ServerInfoValidator.validate_port(80) is True
        assert ServerInfoValidator.validate_port(443) is True
        assert ServerInfoValidator.validate_port(65535) is True
        assert ServerInfoValidator.validate_port("22") is True
        assert ServerInfoValidator.validate_port("8080") is True
    
    def test_validate_port_invalid(self):
        """Тест валидации невалидных портов"""
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_port(0)
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_port(65536)
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_port(-1)
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_port("invalid")
    
    def test_validate_username_valid(self):
        """Тест валидации валидных имен пользователей"""
        assert ServerInfoValidator.validate_username("user") is True
        assert ServerInfoValidator.validate_username("user123") is True
        assert ServerInfoValidator.validate_username("user.name") is True
        assert ServerInfoValidator.validate_username("user_name") is True
        assert ServerInfoValidator.validate_username("user-name") is True
    
    def test_validate_username_invalid(self):
        """Тест валидации невалидных имен пользователей"""
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_username("")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_username("   ")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_username("user@domain")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_username("user name")
        
        with pytest.raises(ValidationError):
            ServerInfoValidator.validate_username("a" * 33)  # Слишком длинное


class TestFileValidator:
    """Тесты для FileValidator"""
    
    def test_validate_file_exists_success(self):
        """Тест успешной проверки существования файла"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            
            result = FileValidator.validate_file_exists(f.name)
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_file_exists_not_found(self):
        """Тест проверки несуществующего файла"""
        with pytest.raises(ValidationError) as exc_info:
            FileValidator.validate_file_exists("nonexistent_file.txt")
        
        assert "Файл не существует" in str(exc_info.value)
    
    def test_validate_file_permissions_read_success(self):
        """Тест успешной проверки прав на чтение"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            result = FileValidator.validate_file_permissions(f.name, "r")
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_file_permissions_write_success(self):
        """Тест успешной проверки прав на запись"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            result = FileValidator.validate_file_permissions(f.name, "w")
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_file_permissions_rw_success(self):
        """Тест успешной проверки прав на чтение и запись"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            result = FileValidator.validate_file_permissions(f.name, "rw")
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_ssh_key_success(self):
        """Тест успешной валидации SSH ключа"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("""-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAFwAAAAdzc2gtcn
NhAAAAAwEAAQAAAQEA1234567890abcdef...
-----END OPENSSH PRIVATE KEY-----""")
            f.flush()
            
            result = FileValidator.validate_ssh_key(f.name)
            assert result is True
            
            os.unlink(f.name)
    
    def test_validate_ssh_key_invalid_content(self):
        """Тест валидации невалидного SSH ключа"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("This is not a valid SSH key")
            f.flush()
            
            with pytest.raises(ValidationError) as exc_info:
                FileValidator.validate_ssh_key(f.name)
            
            assert "не является валидным SSH ключом" in str(exc_info.value)
            
            os.unlink(f.name)
    
    def test_validate_ssh_key_not_found(self):
        """Тест валидации несуществующего SSH ключа"""
        with pytest.raises(ValidationError) as exc_info:
            FileValidator.validate_ssh_key("nonexistent_key.pem")
        
        assert "Файл не существует" in str(exc_info.value)


class TestDataValidator:
    """Тесты для DataValidator"""
    
    def test_validate_required_fields_success(self):
        """Тест успешной проверки обязательных полей"""
        data = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3"
        }
        required_fields = ["field1", "field2", "field3"]
        
        result = DataValidator.validate_required_fields(data, required_fields)
        assert result is True
    
    def test_validate_required_fields_missing(self):
        """Тест проверки с отсутствующими полями"""
        data = {
            "field1": "value1",
            "field2": "value2"
        }
        required_fields = ["field1", "field2", "field3", "field4"]
        
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_required_fields(data, required_fields)
        
        assert "Отсутствуют обязательные поля" in str(exc_info.value)
        assert "field3" in str(exc_info.value)
        assert "field4" in str(exc_info.value)
    
    def test_validate_required_fields_none_values(self):
        """Тест проверки с None значениями"""
        data = {
            "field1": "value1",
            "field2": None,
            "field3": "value3"
        }
        required_fields = ["field1", "field2", "field3"]
        
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_required_fields(data, required_fields)
        
        assert "Отсутствуют обязательные поля" in str(exc_info.value)
        assert "field2" in str(exc_info.value)
    
    def test_validate_field_types_success(self):
        """Тест успешной проверки типов полей"""
        data = {
            "string_field": "value",
            "int_field": 123,
            "float_field": 45.67,
            "bool_field": True,
            "list_field": [1, 2, 3]
        }
        field_types = {
            "string_field": str,
            "int_field": int,
            "float_field": float,
            "bool_field": bool,
            "list_field": list
        }
        
        result = DataValidator.validate_field_types(data, field_types)
        assert result is True
    
    def test_validate_field_types_invalid(self):
        """Тест проверки с невалидными типами"""
        data = {
            "string_field": 123,  # Должно быть str
            "int_field": "not_a_number"  # Должно быть int
        }
        field_types = {
            "string_field": str,
            "int_field": int
        }
        
        with pytest.raises(ValidationError) as exc_info:
            DataValidator.validate_field_types(data, field_types)
        
        assert "Поле 'string_field' должно быть типа str" in str(exc_info.value)
    
    def test_validate_field_types_missing_field(self):
        """Тест проверки с отсутствующим полем"""
        data = {
            "string_field": "value"
        }
        field_types = {
            "string_field": str,
            "missing_field": int  # Отсутствует в данных
        }
        
        result = DataValidator.validate_field_types(data, field_types)
        assert result is True  # Отсутствующие поля не проверяются


class TestValidateConfigFile:
    """Тесты для функции validate_config_file"""
    
    def test_validate_config_file_success(self):
        """Тест успешной валидации конфигурационного файла"""
        # Создаем мок класс Pydantic
        class MockConfig:
            def __init__(self, **kwargs):
                self.data = kwargs
            
            @classmethod
            def from_yaml(cls, file_path):
                return cls(test="value")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
            test: value
            """)
            f.flush()
            
            result = validate_config_file(f.name, MockConfig)
            assert isinstance(result, MockConfig)
            assert result.data == {"test": "value"}
            
            os.unlink(f.name)
    
    def test_validate_config_file_invalid_yaml(self):
        """Тест валидации невалидного YAML файла"""
        class MockConfig:
            pass
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
            test: [unclosed list
            """)
            f.flush()
            
            with pytest.raises(ValidationError) as exc_info:
                validate_config_file(f.name, MockConfig)
            
            assert "Ошибка валидации конфигурации" in str(exc_info.value)
            
            os.unlink(f.name)
    
    def test_validate_config_file_pydantic_validation_error(self):
        """Тест валидации с ошибкой Pydantic"""
        from pydantic import BaseModel, ValidationError as PydanticValidationError
        
        class MockConfig(BaseModel):
            required_field: str
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
            missing_field: value
            """)
            f.flush()
            
            with patch('yaml.safe_load', return_value={"missing_field": "value"}):
                with patch.object(MockConfig, '__init__', side_effect=PydanticValidationError([], MockConfig)):
                    with pytest.raises(ValidationError) as exc_info:
                        validate_config_file(f.name, MockConfig)
                    
                    assert "Ошибка валидации конфигурации" in str(exc_info.value)
            
            os.unlink(f.name)


if __name__ == "__main__":
    pytest.main([__file__])
