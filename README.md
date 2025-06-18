# production
[![badge](https://img.shields.io/badge/license-MIT-blue)](https://github.com/usermicrodevices/prod/blob/main/LICENSE)
django shop based on web-admin interface, also you can clone and
build multiplatform frontend ["prod-flet"](https://github.com/usermicrodevices/prod-flet/)

![image](./screen.png "main screen")

# installation
```
sudo apt install postgresql
sudo -u postgres createuser --superuser prod_user
sudo -u postgres createdb --owner=prod_user prod_database
git clone git@github.com:usermicrodevices/prod.git
cd prod
mkdir logs media static
python -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
./manage.py collectstatic
./manage.py makemigrations
./manage.py migrate
./manage.py createsuperuser --username superuser
./manage.py default_data
```
tool ```default_data``` create 2 demo users with passwords "admin":"admin" and "kassa":"kassa", later you can change it

# running
```
./manage.py runserver --noasgi
```
and go to your browser http://127.0.0.1:8000/admin

# run with daphne
```
daphne -e ssl:interface=127.0.0.1:9443:privateKey=ssl-cert-snakeoil.key:certKey=ssl-cert-snakeoil.pem shop.asgi:application
```
and go to your browser https://127.0.0.1:9443/admin

# OPTIONAL get sales receipt as PDF format
```
sudo apt install texlive-xetex, wkhtmltopdf, pandoc
```

# OPTIONAL use thumbnail images
```
sudo apt install libpng-dev libjpeg-dev libtiff-dev imagemagick
```

# OPTIONAL use qrcode printer
```
pip install qrcode
```

# SOCIALS
[telegram](https://t.me/github_prod)


# Brief description

1. Ability to divide users by roles,
roles are created from any set of fields and permissions of system models.
Permissions are grouped and the group is assigned to a role.
In the basic version, 2 roles are configured: administrator and cashier.

2. Adding reference information about products, companies, points of sale (warehouses), customers.
Generation and printing of price tags, barcodes, QR codes. Printed forms are customizable through templates.
Ability to add any reference information for further use in searching and filtering.
The product stores an unlimited number of images, icon generation from the first image.
Additional tools include barcode correction and price copying.
For ease of filtering and searching in the product directory,
it is necessary to fill out the directory of manufacturers and product models.

3. Documents are divided into types created by the user, for example: receipts, expenses, orders, balances.
Each type has accounting attributes of receipt or expense, auto-registration for settlements, etc.
Printed forms are customized and stored in the print templates section.
Print form templates are customized in HTML format, include CSS.
Excel uploads and downloads are pre-configured, but can be quickly cloned into new ones.
Additional tools include viewing profits and combining multiple documents of the same type into a single document.

4. REST API for working with cash register equipment: POS terminals, scales, etc.
The multi-platform client supports working with scales out of the box.
The mobile version includes a barcode / QR code scanner.
The desktop version works with keyboard scanners in quick search mode.
Support for offline work with periodic synchronization with the server.
Maintaining a customer directory.
Adding customer orders, pre-ordering the supplier.

5. This software can be used as a separate ERP/CRM system,
or implemented or integrated with other accounting (retail,
inventory management, warehouse and etc.) systems.

# Краткое описание

1. Возможность разделять пользователей по ролям,
роли создаются из любого набора полей и разрешений моделей системы.
Разрешения группируются и группа присваивается роли.
В базовой версии настроены 2 роли: администратор и кассир.

2. Добавление справочной информации о товарах, компаниях, точках продаж (складах), покупателях.
Генерация и печать ценников, штрихкодов, qr-кодов. Печатные формы настраиваемые через шаблоны.
Возможность добавлять любую справочную информацию для дальнейшего использования в поиске и фильтрации.
Товар хранит неограниченное количество изображений, генерация иконки из первого изображения.
Дополнительные инструменты содержат исправление штрихкодов и копирование цен.
Для добства фильтрации и поиска в справочнике товаров, необходимо заполнять
справочник производителей и моделей продукции

3. Документы делятся на типы созданные пользователем, например: приходные, расходные, заказы, остатки.
Каждый тип имеет признаки учёта приход или расход, авто-регистрация для расчётов и т.д.
Печатные формы настраиваются и хранятся в разделе шаблонов печати.
Шаблоны печатных форм настраиваются в формате HTML, включая CSS.
Выгрузки и загрузки в Excel преднастроенные, но могут быть быстро клонированы в новые.
Дополнительные инструменты содержат просмотр прибыли и объединение нескольких документов одного типа в общий документ.

4. REST API для работы с кассовым оборудованием: POS терминалы, весы и т.д.
Мультиплатформенный клиент поддерживает работу с весами из коробки.
Мобильная версия включает сканер штрихкодов / qr-кодов.
Десктоп версия работает с клавиатурными сканерами в режиме быстрого поиска.
Поддержка оффлайн работы с периодической синхронизацией с сервером.
Ведение справочника покупателей.
Добавление заказов покупателей, предварительный заказ поставщику.

5. Это программное обеспечение можно использовать как отдельную ERP/CRM систему,
так и внедрять или интегрировать вместе с другими учётными (розничная торговля,
управление запасами, складскими и пр.) системами.
