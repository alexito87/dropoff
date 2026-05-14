# create_modules.ps1
# Скрипт для создания структуры модульного монолита Dropoff

# Список модулей
$modules = "auth","users","catalog","items","orders","payments","rentals","notifications"

foreach ($m in $modules) {
    # Создание корневой папки модуля
    New-Item -ItemType Directory -Path $m -Force

    # Создание подпапок
    New-Item -ItemType Directory -Path "$m\models" -Force
    New-Item -ItemType Directory -Path "$m\controllers" -Force
    New-Item -ItemType Directory -Path "$m\routes" -Force
    New-Item -ItemType Directory -Path "$m\services" -Force

    # Создание __init__.py в каждой папке
    New-Item -ItemType File -Path "$m\__init__.py" -Force
    New-Item -ItemType File -Path "$m\models\__init__.py" -Force
    New-Item -ItemType File -Path "$m\controllers\__init__.py" -Force
    New-Item -ItemType File -Path "$m\routes\__init__.py" -Force
    New-Item -ItemType File -Path "$m\services\__init__.py" -Force
}

Write-Host "Структура модулей Dropoff создана успешно!"