clear

printf "\nInstalling globally.\n\n"
sudo pip3.11 install --upgrade oxi

printf "\nInstalling for current user.\n\n"
pip3.11 install --upgrade oxi

# printf "\nInstalling in virtual environment.\n\n"
# . venv/bin/activate
# pip3 install --upgrade oxi
# deactivate

printf "\n\nEnd of procedures.\n\n"


