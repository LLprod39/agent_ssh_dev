"""
Генератор команд Linux для различных задач
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from ..utils.logger import StructuredLogger


@dataclass
class CommandTemplate:
    """Шаблон команды"""
    
    name: str
    description: str
    command: str
    parameters: List[str]
    health_check: str
    rollback_command: Optional[str] = None
    os_specific: bool = False
    os_types: List[str] = None
    
    def __post_init__(self):
        if self.os_types is None:
            self.os_types = ["ubuntu", "debian", "centos", "rhel"]


class LinuxCommandGenerator:
    """
    Генератор команд Linux для автоматизации
    
    Основные возможности:
    - Генерация команд для установки пакетов
    - Команды для управления сервисами
    - Команды для работы с файлами и директориями
    - Команды для сетевых операций
    - Health-check команды
    """
    
    def __init__(self):
        self.logger = StructuredLogger("LinuxCommandGenerator")
        self.command_templates = self._initialize_command_templates()
    
    def _initialize_command_templates(self) -> Dict[str, List[CommandTemplate]]:
        """Инициализация шаблонов команд"""
        return {
            "package_management": [
                CommandTemplate(
                    name="update_packages",
                    description="Обновление списка пакетов",
                    command="sudo apt update",
                    parameters=[],
                    health_check="apt list --upgradable | wc -l",
                    os_types=["ubuntu", "debian"]
                ),
                CommandTemplate(
                    name="install_package",
                    description="Установка пакета",
                    command="sudo apt install -y {package_name}",
                    parameters=["package_name"],
                    health_check="dpkg -l | grep {package_name}",
                    rollback_command="sudo apt remove -y {package_name}",
                    os_types=["ubuntu", "debian"]
                ),
                CommandTemplate(
                    name="install_package_centos",
                    description="Установка пакета (CentOS/RHEL)",
                    command="sudo yum install -y {package_name}",
                    parameters=["package_name"],
                    health_check="rpm -q {package_name}",
                    rollback_command="sudo yum remove -y {package_name}",
                    os_types=["centos", "rhel"]
                )
            ],
            "service_management": [
                CommandTemplate(
                    name="start_service",
                    description="Запуск сервиса",
                    command="sudo systemctl start {service_name}",
                    parameters=["service_name"],
                    health_check="systemctl is-active {service_name}",
                    rollback_command="sudo systemctl stop {service_name}",
                    os_specific=False
                ),
                CommandTemplate(
                    name="enable_service",
                    description="Включение автозапуска сервиса",
                    command="sudo systemctl enable {service_name}",
                    parameters=["service_name"],
                    health_check="systemctl is-enabled {service_name}",
                    rollback_command="sudo systemctl disable {service_name}",
                    os_specific=False
                ),
                CommandTemplate(
                    name="restart_service",
                    description="Перезапуск сервиса",
                    command="sudo systemctl restart {service_name}",
                    parameters=["service_name"],
                    health_check="systemctl is-active {service_name}",
                    os_specific=False
                )
            ],
            "file_operations": [
                CommandTemplate(
                    name="create_directory",
                    description="Создание директории",
                    command="mkdir -p {directory_path}",
                    parameters=["directory_path"],
                    health_check="test -d {directory_path}",
                    rollback_command="rmdir {directory_path}",
                    os_specific=False
                ),
                CommandTemplate(
                    name="create_file",
                    description="Создание файла",
                    command="touch {file_path}",
                    parameters=["file_path"],
                    health_check="test -f {file_path}",
                    rollback_command="rm -f {file_path}",
                    os_specific=False
                ),
                CommandTemplate(
                    name="copy_file",
                    description="Копирование файла",
                    command="cp {source_path} {destination_path}",
                    parameters=["source_path", "destination_path"],
                    health_check="test -f {destination_path}",
                    rollback_command="rm -f {destination_path}",
                    os_specific=False
                )
            ],
            "network_operations": [
                CommandTemplate(
                    name="check_connectivity",
                    description="Проверка сетевого соединения",
                    command="ping -c 3 {host}",
                    parameters=["host"],
                    health_check="ping -c 1 {host} > /dev/null 2>&1",
                    os_specific=False
                ),
                CommandTemplate(
                    name="download_file",
                    description="Загрузка файла",
                    command="wget -O {output_file} {url}",
                    parameters=["output_file", "url"],
                    health_check="test -f {output_file}",
                    rollback_command="rm -f {output_file}",
                    os_specific=False
                ),
                CommandTemplate(
                    name="curl_request",
                    description="HTTP запрос",
                    command="curl -I {url}",
                    parameters=["url"],
                    health_check="curl -s -o /dev/null -w '%{http_code}' {url} | grep -E '^[23][0-9][0-9]$'",
                    os_specific=False
                )
            ],
            "system_checks": [
                CommandTemplate(
                    name="check_disk_space",
                    description="Проверка дискового пространства",
                    command="df -h",
                    parameters=[],
                    health_check="df -h | awk 'NR>1 {gsub(/%/, \"\", $5); if($5 > 90) exit 1}'",
                    os_specific=False
                ),
                CommandTemplate(
                    name="check_memory",
                    description="Проверка памяти",
                    command="free -h",
                    parameters=[],
                    health_check="free | awk 'NR==2{printf \"%.2f%%\", $3*100/$2}' | sed 's/%//' | awk '$1 > 90 {exit 1}'",
                    os_specific=False
                ),
                CommandTemplate(
                    name="check_cpu_load",
                    description="Проверка загрузки CPU",
                    command="uptime",
                    parameters=[],
                    health_check="uptime | awk '{print $10}' | sed 's/,//' | awk '$1 > 5.0 {exit 1}'",
                    os_specific=False
                )
            ]
        }
    
    def generate_install_commands(self, package_name: str, os_type: str = "ubuntu") -> List[str]:
        """Генерация команд для установки пакета"""
        commands = []
        
        if os_type in ["ubuntu", "debian"]:
            commands.extend([
                "sudo apt update",
                f"sudo apt install -y {package_name}",
                f"dpkg -l | grep {package_name}"
            ])
        elif os_type in ["centos", "rhel"]:
            commands.extend([
                "sudo yum update -y",
                f"sudo yum install -y {package_name}",
                f"rpm -q {package_name}"
            ])
        
        return commands
    
    def generate_service_commands(self, service_name: str, action: str = "start") -> List[str]:
        """Генерация команд для управления сервисом"""
        commands = []
        
        if action == "start":
            commands.extend([
                f"sudo systemctl start {service_name}",
                f"sudo systemctl enable {service_name}",
                f"systemctl is-active {service_name}"
            ])
        elif action == "stop":
            commands.extend([
                f"sudo systemctl stop {service_name}",
                f"systemctl is-active {service_name}"
            ])
        elif action == "restart":
            commands.extend([
                f"sudo systemctl restart {service_name}",
                f"systemctl is-active {service_name}"
            ])
        
        return commands
    
    def generate_nginx_setup_commands(self) -> List[str]:
        """Генерация команд для настройки Nginx"""
        return [
            "sudo apt update",
            "sudo apt install -y nginx",
            "sudo systemctl start nginx",
            "sudo systemctl enable nginx",
            "sudo systemctl status nginx",
            "curl -I http://localhost",
            "nginx -t"
        ]
    
    def generate_docker_setup_commands(self) -> List[str]:
        """Генерация команд для настройки Docker"""
        return [
            "sudo apt update",
            "sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release",
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg",
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
            "sudo apt update",
            "sudo apt install -y docker-ce docker-ce-cli containerd.io",
            "sudo systemctl start docker",
            "sudo systemctl enable docker",
            "sudo usermod -aG docker $USER",
            "docker --version",
            "docker ps"
        ]
    
    def generate_postgresql_setup_commands(self) -> List[str]:
        """Генерация команд для настройки PostgreSQL"""
        return [
            "sudo apt update",
            "sudo apt install -y postgresql postgresql-contrib",
            "sudo systemctl start postgresql",
            "sudo systemctl enable postgresql",
            "sudo -u postgres psql -c 'SELECT version();'",
            "sudo systemctl status postgresql"
        ]
    
    def generate_ssl_certificate_commands(self, domain: str) -> List[str]:
        """Генерация команд для получения SSL сертификата"""
        return [
            "sudo apt update",
            "sudo apt install -y certbot python3-certbot-nginx",
            f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email admin@{domain}",
            "sudo systemctl reload nginx",
            f"curl -I https://{domain}",
            "sudo certbot certificates"
        ]
    
    def generate_health_check_commands(self, service_type: str) -> List[str]:
        """Генерация health-check команд для различных сервисов"""
        health_checks = {
            "nginx": [
                "systemctl is-active nginx",
                "nginx -t",
                "curl -I http://localhost",
                "netstat -tlnp | grep :80"
            ],
            "apache": [
                "systemctl is-active apache2",
                "apache2ctl configtest",
                "curl -I http://localhost",
                "netstat -tlnp | grep :80"
            ],
            "postgresql": [
                "systemctl is-active postgresql",
                "sudo -u postgres psql -c 'SELECT 1;'",
                "netstat -tlnp | grep :5432"
            ],
            "mysql": [
                "systemctl is-active mysql",
                "mysql -e 'SELECT 1;'",
                "netstat -tlnp | grep :3306"
            ],
            "docker": [
                "systemctl is-active docker",
                "docker --version",
                "docker ps",
                "docker system df"
            ],
            "system": [
                "systemctl is-system-running",
                "df -h | awk 'NR>1 {gsub(/%/, \"\", $5); if($5 > 90) exit 1}'",
                "free | awk 'NR==2{printf \"%.2f%%\", $3*100/$2}' | sed 's/%//' | awk '$1 > 90 {exit 1}'",
                "uptime | awk '{print $10}' | sed 's/,//' | awk '$1 > 5.0 {exit 1}'"
            ]
        }
        
        return health_checks.get(service_type, health_checks["system"])
    
    def generate_rollback_commands(self, service_type: str) -> List[str]:
        """Генерация команд отката для различных сервисов"""
        rollback_commands = {
            "nginx": [
                "sudo systemctl stop nginx",
                "sudo systemctl disable nginx",
                "sudo apt remove -y nginx nginx-common"
            ],
            "apache": [
                "sudo systemctl stop apache2",
                "sudo systemctl disable apache2",
                "sudo apt remove -y apache2 apache2-utils"
            ],
            "postgresql": [
                "sudo systemctl stop postgresql",
                "sudo systemctl disable postgresql",
                "sudo apt remove -y postgresql postgresql-contrib"
            ],
            "mysql": [
                "sudo systemctl stop mysql",
                "sudo systemctl disable mysql",
                "sudo apt remove -y mysql-server mysql-client"
            ],
            "docker": [
                "sudo systemctl stop docker",
                "sudo systemctl disable docker",
                "sudo apt remove -y docker-ce docker-ce-cli containerd.io"
            ]
        }
        
        return rollback_commands.get(service_type, [])
    
    def validate_command_safety(self, command: str) -> Dict[str, Any]:
        """Валидация безопасности команды"""
        dangerous_patterns = [
            "rm -rf /",
            "dd if=/dev/zero",
            "mkfs",
            "fdisk",
            "parted",
            "> /dev/sda",
            "chmod 777 /",
            "chown -R root:root /",
            "passwd root",
            "userdel -r",
            "groupdel",
            "killall -9",
            "pkill -9",
            "halt",
            "poweroff",
            "reboot",
            "shutdown"
        ]
        
        command_lower = command.lower().strip()
        is_dangerous = any(pattern in command_lower for pattern in dangerous_patterns)
        
        return {
            "is_safe": not is_dangerous,
            "is_dangerous": is_dangerous,
            "dangerous_patterns": [pattern for pattern in dangerous_patterns if pattern in command_lower],
            "command": command
        }
    
    def get_command_template(self, template_name: str, os_type: str = "ubuntu") -> Optional[CommandTemplate]:
        """Получение шаблона команды по имени"""
        for category, templates in self.command_templates.items():
            for template in templates:
                if template.name == template_name:
                    if not template.os_specific or os_type in template.os_types:
                        return template
        return None
    
    def generate_command_from_template(self, template_name: str, parameters: Dict[str, str], 
                                     os_type: str = "ubuntu") -> Optional[str]:
        """Генерация команды из шаблона"""
        template = self.get_command_template(template_name, os_type)
        if not template:
            return None
        
        try:
            return template.command.format(**parameters)
        except KeyError as e:
            self.logger.error(f"Отсутствует параметр для шаблона {template_name}: {e}")
            return None
    
    def get_available_templates(self, os_type: str = "ubuntu") -> Dict[str, List[str]]:
        """Получение доступных шаблонов команд"""
        available = {}
        for category, templates in self.command_templates.items():
            available[category] = [
                template.name for template in templates 
                if not template.os_specific or os_type in template.os_types
            ]
        return available

