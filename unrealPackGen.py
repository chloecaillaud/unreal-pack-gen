from app import App
import sys

# commandline syntax:
# ./init.py [-defaultPath <path>] [-unrealpakPath <path>]

# default values
basepath = None
packerPath = None

# remove first arg (ie path to program), pre-process the rest
arguments = list(map(lambda arg: arg.strip(), sys.argv[1:]))
# set values
try:
	if '-path' in arguments:
		basepath = arguments[arguments.index('-defaultPath') + 1]
	if '-UpakPath' in arguments:
		packerPath = arguments[arguments.index('-unrealpakPath') + 1]
except IndexError:
	pass

app = App(basepath, packerPath)
app.mainloop()