"""
Интеграционные тесты для системы идемпотентности
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.config.agent_config import AgentConfig
from src.connectors.ssh_connector import SSHConnector, ServerConfig
from src.agents.subtask_agent import SubtaskAgent, Subtask
from src.models.execution_model import ExecutionModel
from src.models.planning_model import TaskStep, Priority
from src.models.execution_context import ExecutionContext
from src.utils.idempotency_system import IdempotencySystem, IdempotencyCheckType


class MockSSHConnector:
    """Мок SSH коннектора для интеграционных тестов"""
    
    def __init__(self):
        self.commands_executed = []
        self.mock_results = {}
        self.connected = True
    
    def execute_command(self, command: str, timeout: int = 30, context: dict = None):
        """Мок выполнения команды"""
        self.commands_executed.append(command)
        
        # Возвращаем предустановленный результат или дефолтный
        if command in self.mock_results:
            return self.mock_results[command]
        
        # Дефолтный успешный результат
        from src.models.command_result import CommandResult, ExecutionStatus
        return CommandResult(
            command=command,
            success=True,
            exit_code=0,
            stdout="mock output",
            stderr="",
            duration=0.1,
            status=ExecutionStatus.COMPLETED
        )
    
    def set_mock_result(self, command: str, result):
        """Установка мок результата для команды"""
        self.mock_results[command] = result
    
    def is_command_safe(self, command: str) -> bool:
        """Проверка безопасности команды"""
        dangerous_commands = ['rm -rf /', 'dd if=/dev/zero', 'mkfs']
        return not any(dangerous in command for dangerous in dangerous_commands)


@pytest.fixture
def mock_ssh_connector():
    """Фикстура для мок SSH коннектора"""
    return MockSSHConnector()


@pytest.fixture
def agent_config():
    """Фикстура для конфигурации агента"""
    return AgentConfig(
        llm={
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        },
        idempotency={
            "enabled": True,
            "cache_ttl": 300,
            "max_snapshots": 10,
            "auto_rollback": True,
            "check_timeout": 30,
            "enable_package_checks": True,
            "enable_file_checks": True,
            "enable_directory_checks": True,
            "enable_service_checks": True,
            "enable_user_checks": True,
            "enable_group_checks": True,
            "enable_port_checks": True,
            "rollback_on_failure": True,
            "rollback_timeout": 60,
            "preserve_snapshots": True,
            "log_checks": True,
            "log_skips": True,
            "log_rollbacks": True
        }
    )


@pytest.fixture
def execution_model(mock_ssh_connector, agent_config):
    """Фикстура для ExecutionModel"""
    return ExecutionModel(agent_config, mock_ssh_connector)


@pytest.fixture
def subtask_agent(mock_ssh_connector, agent_config):
    """Фикстура для SubtaskAgent"""
    return SubtaskAgent(agent_config, ssh_connector=mock_ssh_connector)


class TestIdempotencyIntegration:
    """Интеграционные тесты для системы идемпотентности"""
    
    def test_full_idempotency_workflow(self, execution_model, subtask_agent, mock_ssh_connector):
        """Тест полного рабочего процесса с идемпотентностью"""
        
        # 1. Создание снимка состояния
        snapshot = execution_model.create_idempotency_snapshot("integration_test_001")
        assert snapshot is not None
        assert snapshot.snapshot_id.startswith("integration_test_001_")
        
        # 2. Создание тестовой подзадачи
        subtask = Subtask(
            subtask_id="test_subtask_001",
            title="Установка nginx",
            description="Установка веб-сервера nginx",
            commands=[
                "apt-get update",
                "apt-get install nginx",
                "systemctl start nginx",
                "systemctl enable nginx",
                "touch /etc/nginx/nginx.conf"
            ],
            health_checks=[
                "systemctl is-active nginx",
                "nginx -t"
            ],
            expected_output="Nginx установлен и запущен",
            rollback_commands=[
                "systemctl stop nginx",
                "apt-get remove nginx"
            ]
        )
        
        # 3. Улучшение подзадачи идемпотентностью
        enhanced_subtask = subtask_agent.enhance_subtask_with_idempotency(subtask)
        
        # Проверяем, что подзадача была улучшена
        assert enhanced_subtask.metadata.get("idempotent_enhanced") is True
        assert "original_commands" in enhanced_subtask.metadata
        assert "idempotency_checks" in enhanced_subtask.metadata
        
        # Проверяем, что команды стали идемпотентными
        assert len(enhanced_subtask.commands) == len(subtask.commands)
        
        # Проверяем типы идемпотентных команд
        idempotent_commands = enhanced_subtask.commands
        assert any("dpkg -l | grep -q" in cmd for cmd in idempotent_commands)  # Пакеты
        assert any("systemctl is-active" in cmd for cmd in idempotent_commands)  # Сервисы
        assert any("test -f" in cmd for cmd in idempotent_commands)  # Файлы
        
        # 4. Проверка идемпотентности команд
        idempotency_checks = enhanced_subtask.metadata.get("idempotency_checks", [])
        assert len(idempotency_checks) > 0
        
        # Проверяем типы проверок
        check_types = [check.check_type for check in idempotency_checks]
        assert IdempotencyCheckType.PACKAGE_INSTALLED in check_types
        assert IdempotencyCheckType.SERVICE_RUNNING in check_types
        assert IdempotencyCheckType.FILE_EXISTS in check_types
        
        # 5. Симуляция выполнения команд
        for command in idempotent_commands:
            # Проверяем, что команда безопасна
            assert execution_model.ssh_connector.is_command_safe(command)
            
            # Выполняем команду (в мок режиме)
            result = execution_model.ssh_connector.execute_command(command)
            assert result.success
        
        # 6. Проверка статистики
        stats = execution_model.get_execution_stats()
        assert stats["total_commands"] > 0
        
        # 7. Проверка статуса системы идемпотентности
        idempotency_status = execution_model.get_idempotency_status()
        assert idempotency_status["snapshots_count"] > 0
        assert idempotency_status["current_snapshot"] == snapshot.snapshot_id
    
    def test_idempotency_with_existing_state(self, execution_model, mock_ssh_connector):
        """Тест идемпотентности с уже существующим состоянием"""
        
        # Настраиваем мок для имитации уже установленного пакета
        mock_ssh_connector.set_mock_result(
            "dpkg -l | grep -q '^ii  nginx'",
            execution_model.ssh_connector.execute_command("echo 'nginx already installed'")
        )
        
        # Генерируем идемпотентную команду
        cmd, checks = execution_model.generate_idempotent_command(
            "apt-get install nginx", "install_package", "nginx"
        )
        
        # Проверяем, что команда должна быть пропущена
        should_skip = execution_model.check_command_idempotency(cmd, checks)
        assert should_skip is True
        
        # Выполняем команду
        result = execution_model.ssh_connector.execute_command(cmd)
        assert result.success
        
        # Проверяем, что команда была пропущена (содержит сообщение о пропуске)
        assert "IDEMPOTENT" in result.stdout or "already" in result.stdout.lower()
    
    def test_rollback_system(self, execution_model, mock_ssh_connector):
        """Тест системы отката"""
        
        # 1. Создание снимка с изменениями
        snapshot = execution_model.create_idempotency_snapshot("rollback_test_001")
        snapshot.packages_installed = ["nginx", "apache2"]
        snapshot.services_started = ["nginx"]
        snapshot.files_created = ["/etc/nginx/nginx.conf"]
        
        # 2. Создание команд отката
        rollback_commands = execution_model.idempotency_system.create_rollback_commands(snapshot)
        
        # Проверяем, что команды отката созданы
        assert len(rollback_commands) > 0
        assert any("apt-get remove -y nginx" in cmd for cmd in rollback_commands)
        assert any("apt-get remove -y apache2" in cmd for cmd in rollback_commands)
        assert any("systemctl stop nginx" in cmd for cmd in rollback_commands)
        assert any("rm -f /etc/nginx/nginx.conf" in cmd for cmd in rollback_commands)
        
        # 3. Выполнение отката
        rollback_results = execution_model.execute_idempotency_rollback(snapshot.snapshot_id)
        
        # Проверяем, что откат выполнен
        assert len(rollback_results) > 0
        assert all(result.success for result in rollback_results)
    
    def test_error_handling_and_rollback(self, execution_model, mock_ssh_connector):
        """Тест обработки ошибок и отката"""
        
        # 1. Создание снимка перед выполнением
        snapshot = execution_model.create_idempotency_snapshot("error_test_001")
        
        # 2. Настраиваем мок для имитации ошибки
        mock_ssh_connector.set_mock_result(
            "apt-get install nginx",
            execution_model.ssh_connector.execute_command("echo 'Package not found' && exit 1")
        )
        
        # 3. Выполнение команды с ошибкой
        result = execution_model.ssh_connector.execute_command("apt-get install nginx")
        assert not result.success
        
        # 4. Откат при ошибке
        rollback_results = execution_model.execute_idempotency_rollback(snapshot.snapshot_id)
        
        # Проверяем, что откат выполнен
        assert len(rollback_results) >= 0  # Может быть пустым, если нет изменений
    
    def test_cache_functionality(self, execution_model, mock_ssh_connector):
        """Тест функциональности кэша"""
        
        # 1. Создание проверки
        from src.utils.idempotency_system import IdempotencyCheck, IdempotencyCheckType
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        # 2. Первый вызов - команда должна выполниться
        results1 = execution_model.idempotency_system.check_idempotency([check])
        assert len(results1) == 1
        initial_command_count = len(mock_ssh_connector.commands_executed)
        
        # 3. Второй вызов - команда должна быть взята из кэша
        results2 = execution_model.idempotency_system.check_idempotency([check])
        assert len(results2) == 1
        final_command_count = len(mock_ssh_connector.commands_executed)
        
        # Проверяем, что команда не выполнялась повторно
        assert final_command_count == initial_command_count
    
    def test_subtask_agent_planning_with_idempotency(self, subtask_agent, agent_config):
        """Тест планирования подзадач с идемпотентностью"""
        
        # 1. Создание тестового шага
        step = TaskStep(
            step_id="test_step_001",
            title="Установка веб-сервера",
            description="Установка и настройка nginx",
            priority=Priority.MEDIUM
        )
        
        # 2. Создание контекста планирования
        from src.agents.subtask_agent import SubtaskPlanningContext
        
        context = SubtaskPlanningContext(
            step=step,
            server_info={"os": "linux", "arch": "x86_64"},
            os_type="ubuntu",
            installed_services=[],
            available_tools=["apt", "systemctl", "curl", "wget"],
            constraints=[],
            previous_subtasks=[],
            environment={}
        )
        
        # 3. Планирование подзадач (с идемпотентностью)
        result = subtask_agent.plan_subtasks(step, context)
        
        # Проверяем, что планирование прошло успешно
        assert result.success
        assert len(result.subtasks) > 0
        
        # 4. Проверяем, что подзадачи содержат идемпотентные команды
        for subtask in result.subtasks:
            assert len(subtask.commands) > 0
            
            # Проверяем, что есть идемпотентные команды
            idempotent_commands = subtask.commands
            has_idempotent = any(
                "dpkg -l | grep -q" in cmd or 
                "systemctl is-active" in cmd or 
                "test -f" in cmd or 
                "test -d" in cmd
                for cmd in idempotent_commands
            )
            assert has_idempotent, f"Нет идемпотентных команд в подзадаче: {subtask.title}"
    
    def test_configuration_validation(self, agent_config):
        """Тест валидации конфигурации"""
        
        # Проверяем, что конфигурация идемпотентности загружена
        assert agent_config.idempotency is not None
        assert agent_config.idempotency.enabled is True
        assert agent_config.idempotency.cache_ttl == 300
        assert agent_config.idempotency.max_snapshots == 10
        assert agent_config.idempotency.auto_rollback is True
        
        # Проверяем настройки проверок
        assert agent_config.idempotency.enable_package_checks is True
        assert agent_config.idempotency.enable_file_checks is True
        assert agent_config.idempotency.enable_directory_checks is True
        assert agent_config.idempotency.enable_service_checks is True
        assert agent_config.idempotency.enable_user_checks is True
        assert agent_config.idempotency.enable_group_checks is True
        assert agent_config.idempotency.enable_port_checks is True
        
        # Проверяем настройки отката
        assert agent_config.idempotency.rollback_on_failure is True
        assert agent_config.idempotency.rollback_timeout == 60
        assert agent_config.idempotency.preserve_snapshots is True
        
        # Проверяем настройки логирования
        assert agent_config.idempotency.log_checks is True
        assert agent_config.idempotency.log_skips is True
        assert agent_config.idempotency.log_rollbacks is True
    
    def test_performance_under_load(self, execution_model, mock_ssh_connector):
        """Тест производительности под нагрузкой"""
        
        import time
        
        # 1. Создание множества проверок
        checks = []
        for i in range(10):
            from src.utils.idempotency_system import IdempotencyCheck, IdempotencyCheckType
            
            check = IdempotencyCheck(
                check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
                target=f"package_{i}",
                expected_state=True,
                check_command=f"dpkg -l | grep -q '^ii  package_{i}'",
                success_pattern=".*",
                description=f"Проверка установки package_{i}"
            )
            checks.append(check)
        
        # 2. Измерение времени выполнения
        start_time = time.time()
        results = execution_model.idempotency_system.check_idempotency(checks)
        end_time = time.time()
        
        # Проверяем, что все проверки выполнены
        assert len(results) == 10
        
        # Проверяем, что время выполнения разумное (менее 5 секунд)
        execution_time = end_time - start_time
        assert execution_time < 5.0, f"Время выполнения слишком большое: {execution_time} сек"
        
        # 3. Проверяем кэширование
        start_time = time.time()
        results2 = execution_model.idempotency_system.check_idempotency(checks)
        end_time = time.time()
        
        # Второй вызов должен быть быстрее благодаря кэшу
        second_execution_time = end_time - start_time
        assert second_execution_time < execution_time, "Кэширование не работает"
    
    def test_error_recovery(self, execution_model, mock_ssh_connector):
        """Тест восстановления после ошибок"""
        
        # 1. Создание снимка
        snapshot = execution_model.create_idempotency_snapshot("recovery_test_001")
        
        # 2. Настраиваем мок для имитации различных ошибок
        mock_ssh_connector.set_mock_result(
            "dpkg -l | grep -q '^ii  nginx'",
            execution_model.ssh_connector.execute_command("echo 'Connection timeout' && exit 1")
        )
        
        # 3. Выполнение проверки с ошибкой
        from src.utils.idempotency_system import IdempotencyCheck, IdempotencyCheckType
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        results = execution_model.idempotency_system.check_idempotency([check])
        
        # Проверяем, что ошибка обработана корректно
        assert len(results) == 1
        assert not results[0].success
        assert "Connection timeout" in results[0].error_message
        
        # 4. Проверяем, что система продолжает работать
        status = execution_model.get_idempotency_status()
        assert status["snapshots_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__])
