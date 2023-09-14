from PIL import Image, ImageTk
from math import isclose
from dataManager import DataManager
import customtkinter
import os

# import type defs
from collections.abc import Sequence, Mapping
from customtkinter import CTkFrame
from typing import Callable, Any
from tkinter import Event
from os import PathLike

# since app is intended to be run in a different working dir, CURRENT_FILE_DIR is needed for accessing certain data
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

#---------------------------------------------------------------------------------------------------
class ButtonRowComponent(CTkFrame):
	def __init__(self, master: Any, buttonNames: Sequence[str], buttonCallbacks: Sequence[Callable], buttonThemes: Sequence[dict | None]) -> None:
		super().__init__(master=master, fg_color='transparent')

		if not bool(len(buttonNames) == len(buttonCallbacks) == len(buttonThemes)):
			raise ValueError('missmatched Iteratable length')
		
		self.buttons: Mapping[str, customtkinter.CTkButton] = {}
		for i, buttonName in enumerate(buttonNames, 0):
			self.buttons[buttonName] = customtkinter.CTkButton(master=self, text=buttonName, command=buttonCallbacks[i])
			if buttonThemes[i] != None:
				self.buttons[buttonName].configure(True, **buttonThemes[i])

			self.buttons[buttonName].grid(column=i, row=0, padx=(10,0), pady=10, sticky='ew')

		# layout
		self.columnconfigure(tuple(range(len(buttonNames))), weight=1, uniform='group0')
		self.rowconfigure(0, weight=1, minsize=32)

#-
	def setButtonState(self, buttonName: str, disabled: bool) -> None:
		if disabled:
			state = 'disabled'
		else:
			state = 'normal'

		self.buttons[buttonName].configure(True, **{'state': state})

#---------------------------------------------------------------------------------------------------
class separatorComponent(CTkFrame):
	def __init__(self, master: Any, height: int = 3, width: int = 3, color: str | tuple[str, str] | None = None) -> None:
		""" A separator.\n
		Color: in addition to any str accepted by CTkFrame, passing 'POP' uses the fg_color of the parent's parent
		"""

		if color == 'POP' and isinstance(master, CTkFrame):
			color = self._getColor(master.master)

		super().__init__(master=master, height=height, width=width, fg_color=color)

#-
	def _getColor(self , parent: CTkFrame | customtkinter.CTk) -> None:
		""" Get the frame component's color.\n
		Returns a color equivalent to 'transparent'.
		"""

		if(isinstance(parent, customtkinter.CTk)):
			return parent.cget('fg_color')
		else:
			frameColor = parent._fg_color

			if frameColor == 'transparent':
				return self._getColor(parent.master)
			else:
				return frameColor

#---------------------------------------------------------------------------------------------------
class ImageFilePickerComponent(CTkFrame):
	def __init__(self, master: Any, title: str, pathVar: customtkinter.StringVar, defaultDir: str, dialogTitle: str, imageSize: tuple[int, int], buttonTheme: dict | None = None) -> None:
		super().__init__(master=master, fg_color='transparent')

		self.resultVar = pathVar
		self.defaultDir = defaultDir
		self.dialogTitle = dialogTitle
		self.imageSize = imageSize

		# components
		self.topLabel = customtkinter.CTkLabel(master=self, text=title, justify='left')
		self.button = customtkinter.CTkButton(master=self, text='Choose File', command=self.openFileSelectDialog)
		if buttonTheme != None:
			self.button.configure(True, **buttonTheme)

		# undelying image data
		self.imageData = DataManager.cropAndResizeImage(Image.open(self.resultVar.get() or os.path.join(CURRENT_FILE_DIR, './images/defaultImage.png')), self.imageSize)
		self.image = ImageTk.PhotoImage(self.imageData, width=self.imageSize[0], height=self.imageSize[1])
		self.scaleFac = 1

		# image preview component
		self.imageCanvas = customtkinter.CTkCanvas(master=self, highlightthickness=0, width=self.imageSize[0], height=self.imageSize[1], background=self._getColor(self))
		self.imageID = self.imageCanvas.create_image(0,0, **{'anchor': 'nw', 'image': self.image})
		self.imageCanvas.bind('<Configure>', self._onResizeEvent)

		# layout
		self.topLabel.grid(    column=0, row=0, padx=10, pady=(10, 0),  sticky='nw')
		self.button.grid(      column=0, row=1, padx=10, pady=(0 , 0),  sticky='nw')
		self.imageCanvas.grid(column=0, row=2, padx=10, pady=(10, 10), sticky='nw')

		self.columnconfigure(0, weight=1)

#-
	def openFileSelectDialog(self) -> None:
		""" Open file browser. Returns path to file. """

		# get dialog params
		fileTypes = [('All Supported Types', ('*.png', '*.jpg', '*.jpeg', '*.jfif', '*.pjpeg', '*.pjp')), ('PNG Images', ('*.png')), ('JPEG Images', ('*.jpg', '*.jpeg', '*.jfif', '*.pjpeg', '*.pjp'))]
		initialDir, initialFile = os.path.split(self.resultVar.get())

		dialogResult = customtkinter.filedialog.askopenfilename(filetypes=fileTypes, initialdir=initialDir or self.defaultDir, initialfile=initialFile, parent=self.winfo_toplevel(), title=self.dialogTitle)

		# update with results
		self.resultVar.set(dialogResult)

		self.imageData = DataManager.cropAndResizeImage(Image.open(dialogResult or os.path.join(CURRENT_FILE_DIR, './images/defaultImage.png')), self.imageSize)
		self.image = ImageTk.PhotoImage(self.imageData.resize((int(self.imageSize[0] * self.scaleFac), int(self.imageSize[1] * self.scaleFac))))
		self.imageCanvas.itemconfigure(self.imageID, image=self.image)

#-
	def _getCropResizedImageData(self, image: Image.Image) -> Image.Image:
		""" Crop and resize image to fit specified dims. """

		# if new aspect ratio less than the image's, reduce height else, reduce height
		# prevents bbox extending outside the original image's
		if (self.imageSize[0] / self.imageSize[1]) <= (image.width / image.height):
			newHeight = image.height
			newWidth  = image.height * (self.imageSize[0] / self.imageSize[1])
		else:
			newHeight = image.width * (self.imageSize[1] / self.imageSize[0])
			newWidth  = image.width

		cropBbox = (
			(image.width *0.5) - (newWidth *0.5),
			(image.height*0.5) - (newHeight*0.5),
			(image.width *0.5) - (newWidth *0.5) + newWidth,
			(image.height*0.5) - (newHeight*0.5) + newHeight,
			)
		
		return image.resize(self.imageSize, Image.BICUBIC, cropBbox)

#-
	def _getColor(self , parent: CTkFrame | customtkinter.CTk) -> None:
		""" Get the frame component's color for non CTk components.\n
		Returns a color equivalent to 'transparent'.
		"""

		if(isinstance(parent, customtkinter.CTk)):
			return parent._apply_appearance_mode(parent.cget('fg_color'))
		else:
			frameColor = parent._apply_appearance_mode(parent._fg_color)

			if frameColor == 'transparent':
				return self._getColor(parent.master)
			else:
				return frameColor

#-
	def _onResizeEvent(self, event: Event) -> None:
		""" Uniformly scale the image when window is resized. """

		# smallest scale between directions, min 1
		newScaleFac = min(event.width/self.imageSize[0], event.height/self.imageSize[1], 1)
		# early out if no visal diff between current and rescaled
		if isclose(self.scaleFac, newScaleFac, rel_tol=0.005):
			return

		self.scaleFac = newScaleFac
		self.image = ImageTk.PhotoImage(self.imageData.resize((int(self.imageSize[0] * self.scaleFac), int(self.imageSize[1] * self.scaleFac))))
		self.imageCanvas.itemconfigure(self.imageID, image=self.image)

#---------------------------------------------------------------------------------------------------
class DirectoryPickerComponent(CTkFrame):
	def __init__(self, master: Any, title: str, pathVar: customtkinter.StringVar, defaultDir: str, dialogTitle: str, buttonTheme: dict | None = None) -> None:
		super().__init__(master=master, fg_color='transparent')

		self.resultVar = pathVar
		self.defaultDir = defaultDir
		self.dialogTitle = dialogTitle

		# components
		self.topLabel = customtkinter.CTkLabel(master=self, text=title, justify='left')
		self.button = customtkinter.CTkButton(master=self, text='Choose Folder', command=self.openDirSelectDialog)
		if buttonTheme != None:
			self.button.configure(True, **buttonTheme)

		self.pathLabel = customtkinter.CTkLabel(master=self, text='', justify='left')

		# layout
		self.topLabel.grid( column=0, row=0, padx=10, pady=(10, 5),  sticky='nw')
		self.button.grid(   column=0, row=1, padx=10, pady=(0 , 0),  sticky='nw')
		self.pathLabel.grid(column=0, row=2, padx=10, pady=(10, 10), sticky='nw')

		self.columnconfigure(0, weight=1)

#-
	def openDirSelectDialog(self) -> None:
		""" Open file browser. Returns path to dir. """

		initialDir, _ = os.path.split(self.resultVar.get())
		dialogResult = customtkinter.filedialog.askdirectory(initialdir=initialDir or self.defaultDir, mustexist=True, parent=self.winfo_toplevel(), title=self.dialogTitle)

		# update with results
		self.resultVar.set(dialogResult)
		self.pathLabel.configure(True, **{'text': self._truncatePath(dialogResult)})

#-
	def _truncatePath(self, path: PathLike[str], segCount: int = 2) -> str:
		fullPath = os.path.abspath(path)
		driveLetter = os.path.splitdrive(fullPath)[0]

		# get 2 last path segments
		sepIndex = len(fullPath)
		for i in range(0, segCount):
			sepIndex = fullPath.rfind('\\', 0, sepIndex)

		if sepIndex == -1 or fullPath.rfind('\\', 0, sepIndex) == -1:
			# path has <= path segs than specified
			return fullPath
		else:
			return driveLetter + '\\' + '...' + fullPath[sepIndex:]

#---------------------------------------------------------------------------------------------------
class OptionMenuWithLabel(CTkFrame):
	def __init__(self, master: Any, text: str, options: list[str], optionMenuTheme: dict | None = None) -> None:
		super().__init__(master=master, fg_color='transparent')

		self.text = text

		# components
		self.label = customtkinter.CTkLabel(master=self, text=self.text, justify='right')
		self.optionMenu = customtkinter.CTkOptionMenu(master=self, values=options)
		self.optionMenu.configure(True, **optionMenuTheme)

		self.label.grid(column=0, row=0, padx=0, pady=0, sticky='ne')
		self.optionMenu.grid(column=1, row=0, padx=(20, 0), pady=0, sticky='ne')

		self.columnconfigure(1, minsize=280, weight=1)
		self.columnconfigure(0, weight=1)

#-
	def get(self) -> str:
		return self.optionMenu.get()


#---------------------------------------------------------------------------------------------------
class InfoModalWindow(customtkinter.CTkToplevel):
	def __init__(self, parent: Any, text: str) -> None:
		self.parent = parent

		# 'disable' main window
		self.parent.wm_attributes('-disable', True)
		
		super().__init__()
		self.resizable(False, False)
		self.title('info')

		# redirect focus to modal when attemting to return to main window
		self.transient(master=self.parent)

		# text and img frame
		self.msgFrame = CTkFrame(master=self, fg_color='transparent')
		self.msgFrame.grid(column=0, row=0, padx=20, pady=10, sticky='new')
		# img
		self.image = customtkinter.CTkImage(Image.open(os.path.join(CURRENT_FILE_DIR, './images/icon_info.png')), size=(32,32))
		self.imageComponent = customtkinter.CTkLabel(master=self.msgFrame, text='', image=self.image)
		self.imageComponent.grid(column=0, row=0, padx=0, pady=0, sticky='nw')
		# text
		self.msgLabel = customtkinter.CTkLabel(master=self.msgFrame, text=text, height= 50, font=customtkinter.CTkFont(size=18, weight='bold'), justify='left')
		self.msgLabel.grid(column=1, row=0, padx=0, pady=0, sticky='nsew')
		# frame layout
		self.msgFrame.columnconfigure(0, minsize=64)
		self.msgFrame.columnconfigure(1, weight=1)
		self.msgFrame.rowconfigure(0, weight=1)

		# button
		self.okButton = customtkinter.CTkButton(master=self, text='ok', command=self.close)
		self.okButton.grid(column=0, row=1, padx=20, pady=10, sticky='s')

		# layout
		self.columnconfigure(0, weight=1)


		self.update()
		newWidth  = max(300, self.msgLabel.winfo_reqwidth() + 10)
		newHeight = max(120, self.msgLabel.winfo_reqheight())
		self.geometry(self.__getGeomtryString(newWidth, newHeight))

		# bind windows deletion to the close func
		self.protocol('WM_DELETE_WINDOW', self.close)

#-
	def close(self) -> None:
		# re 'enable' main window
		self.parent.wm_attributes('-disable', False)
		self.destroy()

#-
	def __getGeomtryString(self, width: int, height: int) -> str:
		""" Return the position and dims for the window relative to the parent. """

		xPos = int(self.parent.winfo_x() + (self.parent.winfo_width()  / 2))
		yPos = int(self.parent.winfo_y() + (self.parent.winfo_height() / 2))

		return f'{width}x{height}+{xPos}+{yPos}'