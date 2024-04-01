# https://seleniumhq.github.io/selenium/docs/api/py/
# https://www.seleniumhq.org/docs/04_webdriver_advanced.jsp
# https://intoli.com/tags/selenium/
# 

# mount the vm in the host
# mkdir -pv ~/selenium && sshfs -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3,port=2222,password_stdin user@localhost:/home/user/ ~/selenium <<<"password"
# but first install ssh-server (if not already)
# su -c 'apt-get install openssh-server'

su -c 'apt-get install xvfb firefox-esr'

wget https://bootstrap.pypa.io/get-pip.py -O get-pip.py
su -c 'python get-pip.py'

su -c 'pip install selenium'

su -c 'pip install PyVirtualDisplay'


wget https://github.com/mozilla/geckodriver/releases/download/v0.24.0/geckodriver-v0.24.0-linux64.tar.gz
tar -x geckodriver -zf geckodriver-v0.24.0-linux64.tar.gz
su -c 'mv geckodriver /usr/bin/geckodriver'


# try it

cat <<-EOF | python
	from pyvirtualdisplay import Display
	from selenium import webdriver
	display = Display(visible=0, size=(800, 600))
	display.start()
	browser = webdriver.Firefox()
	browser.get('https://seleniumhq.github.io/selenium/docs/api/py/')
	print browser.title
	browser.quit()
	display.stop()
EOF

# or

export DISPLAY=:1
Xvfb $DISPLAY -screen 0 1920x1080x16 &
# disown
cat <<-EOF | python
	from selenium import webdriver
	browser = webdriver.Firefox()
	browser.get('https://www.seleniumhq.org/docs/04_webdriver_advanced.jsp')
	print browser.title
	browser.quit()
EOF


