# Finalizar install.sh

In main page, stop all unwanted strategies
Call for balance
Add the following into moTrade crontab
    */10 * * * * curl -k https://motrade.mooo.com/process/
    1 1 * * * curl -k https://motrade.mooo.com/balance/
All set!

how to: crontab -l | { cat; echo "0 0 0 0 0 some entry"; } | crontab -


y enable updates on ubuntu crontab 


# mover entorno de test a repo nuevo. Liquidar el repo viejo llegado el momento.
- parar procesos crontab
- parar apache y servicio
- guardar copia del directorio actual (ojo a la BD!)
- subir claves a motradebot
- clonar repo desde motradebot
- enchufar la BD en su sitio
- arrancar apache y BINGX
- probar procesos cron
- habilitar procesos cron
- si todo funciona, ese ya es el repo nuevo

# mejoras antes de salir
user profile page - bet limit
user profile page - enable/disable process. O en home page mejor?
                  - https://www.w3schools.com/howto/howto_css_switch.asp
home page         - improve version banner
home page         - add indicators : isMarketopen. Is proccess enabled?

# otras mejoras
real vs test account - change from web?

# Documentacion. 
manual de uso. explicación de todo

# Mover Esto a issues.

