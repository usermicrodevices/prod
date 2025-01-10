# production
[![badge](https://img.shields.io/badge/license-MIT-blue)](https://github.com/usermicrodevices/prod/blob/main/LICENSE)
django shop
![image](./screen.png "main screen")

# installation
```
git clone git@github.com:usermicrodevices/prod.git
cd prod
mkdir logs media static
python -m venv venv
. ./venv/bin/activate
pip install -r requirements
./manage.py collectstatic
./manage.py makemigrations
./manage.py migrate
./manage.py createsuperuser
```

# running
```
./manage.py runserver
```
and go to your browser http://127.0.0.1:8000/admin
