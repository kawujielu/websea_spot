ps -ef | grep Chrome | grep -v grep  | awk '{print "kill -9 "$2}'  | sh
pkill chromedriver
