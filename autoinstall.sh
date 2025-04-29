clear

printf "\nInstalling globally.\n\n"
sudo pip3.11 install --upgrade pybase3

printf "\nInstalling for current user.\n\n"
pip3.11 install --upgrade pybase3

printf "\nInstalling in virtual environment.\n\n"
. venv/bin/activate
pip3 install --upgrade pybase3
deactivate

printf "\n\nEnd of procedures.\n\n"


