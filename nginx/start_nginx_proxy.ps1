# Script PowerShell para construir y levantar el proxy Nginx
# Ejecuta esto desde la raíz del proyecto

docker build -t dep_nginx_proxy ./nginx

docker run -d --name dep_nginx_proxy -p 80:80 --network=host dep_nginx_proxy
