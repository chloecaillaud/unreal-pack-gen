from dataManager import DataManager
from customComponents import *
from PIL import Image
import customtkinter
import json
import os
import gc

# import type defs
from collections.abc import Mapping
from os import PathLike


# since app is intended to be run in a different working dir, CURRENT_FILE_DIR is needed for accessing certain data
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# app
class App(customtkinter.CTk):
	def __init__(self, basePath: PathLike[str] | None, unrealPakPath = PathLike[str] | None) -> None:
		super().__init__()

		# define theme
		customtkinter.set_appearance_mode('system')
		customtkinter.set_default_color_theme('blue')
		self.customColors = DataManager.fetchJsonData(os.path.join(CURRENT_FILE_DIR, './settings/customColors.json')) or dict()
		
		# initalize DataManager
		self.dataManager = DataManager(
			 basePath or os.getcwd()
			,os.path.join(CURRENT_FILE_DIR, './settings/packLayout.json')
			,os.path.join(CURRENT_FILE_DIR, './settings/assetTypeTable.json')
			,os.path.join(CURRENT_FILE_DIR, './settings/packAdditions/')
			,unrealPakPath
			)
		
		# define default dim
		self.defaultDim = '600x800'
		self.geometry(self.defaultDim)
		self.resizable(True, True)
		
		# set info
		self.title('unreal pack generator')

		# initalize all other vars
		self.currentMainFrame = None
		self.prevSteps = []

		self.inputVars: Mapping[str, customtkinter.Variable] = {}
		self.components: Mapping[str, Any] = {}

		self.unknownFiles = None
		self.unfinishedJobCount = 0

		self.registerValidators()

		# display first window content
		self.displayInfoInput()

#---
# main window contents
	
	def displayInfoInput(self) -> None:
		self.resetMainFrame()
		self.geometry('680x850')

		self.currentMainFrame.columnconfigure(0, weight=1)

		self.components['labelTitle'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Pack info:', justify='left', font=customtkinter.CTkFont(size=25, weight= 'bold'))
		self.components['labelTitle'].grid(column=0, row=0, padx=20, pady=(15,5), sticky='sw')

		# ---
		self.components['sep0'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep0'].grid(column=0, row=1, padx=20, pady=10, sticky='ew')
		
		# name / version
		frame0 = self.components['frame0'] = customtkinter.CTkFrame(master=self.currentMainFrame, fg_color='transparent')
		frame0.grid(column=0, row=2, sticky='nsew')
		frame0.columnconfigure(0, weight=3)
		frame0.columnconfigure(1, weight=1)

		self.components['warnTextName'] = customtkinter.CTkLabel(master=frame0, height=10, text='', justify='left', font=customtkinter.CTkFont(size=12))
		self.components['labelName'] = customtkinter.CTkLabel(master=frame0, height=30, text='Name*', justify='left')
		self.components['inputName'] = customtkinter.CTkEntry(master=frame0, placeholder_text='A name for the pack.', validate='focusout', validatecommand=self.validateName)
		self.components['inputName'].configure(True, **self.customColors['normalEntry'])
		self.components['labelName'].grid(column=0, row=0, padx=20, pady=(0,0), sticky='sw')
		self.components['inputName'].grid(column=0, row=1, padx=20, pady=(0,0), sticky='new')
		self.components['warnTextName'].grid(column=0, row=2, padx=(20,0), pady=(5,10), sticky='nw')

		self.components['warnTextVersion'] = customtkinter.CTkLabel(master=frame0, height=10, text='', justify='left', font=customtkinter.CTkFont(size=12))
		self.components['labelVersion'] = customtkinter.CTkLabel(master=frame0, height=30, text='Version*', justify='left')
		self.components['inputVersion'] = customtkinter.CTkEntry(master=frame0, placeholder_text='1.0', validate='focusout', validatecommand=self.validateVersion)
		self.components['inputVersion'].configure(True,**self.customColors['normalEntry'])
		self.components['labelVersion'].grid(column=1, row=0, padx=20, pady=(0,0), sticky='sw')
		self.components['inputVersion'].grid(column=1, row=1, padx=20, pady=(0,0), sticky='new')
		self.components['warnTextVersion'].grid(column=1, row=2, padx=(20,0), pady=(5,10), sticky='nw')

		# description
		self.components['labelDesc'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Pack description', justify='left')
		self.components['inputDesc'] = customtkinter.CTkTextbox(master=self.currentMainFrame, height=100, wrap='word')
		self.components['inputDesc'].configure(True, **self.customColors['customTextbox'])
		self.components['labelDesc'].grid(column=0, row=3, padx=20, pady=(0,0 ), sticky='sw')
		self.components['inputDesc'].grid(column=0, row=4, padx=20, pady=(0,10), sticky='new')

		# category / tags
		frame1 = self.components['frame1'] = customtkinter.CTkFrame(master=self.currentMainFrame, fg_color='transparent')
		frame1.grid(column=0, row=5, sticky='nsew')
		frame1.columnconfigure(0, weight=1)
		frame1.columnconfigure(1, weight=3)

		self.components['labelCategory'] = customtkinter.CTkLabel(master=frame1, text='Content category*', justify='left')
		self.components['inputCategory'] = customtkinter.CTkOptionMenu(master=frame1, values=['Content', 'Blueprint'], height=30)
		self.components['inputCategory'].configure(True, **self.customColors['customOptionMenu'])
		self.components['labelCategory'].grid(column=0, row=0, padx=20, pady=(0,0 ), sticky='sw')
		self.components['inputCategory'].grid(column=0, row=1, padx=20, pady=(0,10), sticky='new')

		self.components['labelTags'] = customtkinter.CTkLabel(master=frame1, text='Tags (separated by commas)', justify='left')
		self.components['inputTags'] = customtkinter.CTkEntry(master=frame1, height=30, placeholder_text='props, interior, pbr')
		self.components['inputTags'].configure(True, **self.customColors['normalEntry'])
		self.components['labelTags'].grid(column=1, row=0, padx=20, pady=(0,0 ), sticky='sw')
		self.components['inputTags'].grid(column=1, row=1, padx=20, pady=(0,10), sticky='new')

		#---
		self.components['sep1'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep1'].grid(column=0, row=6, padx=20, pady=5, sticky='ew')
		
		# image select
		frame2 = self.components['frame2'] = customtkinter.CTkFrame(master=self.currentMainFrame, fg_color='transparent')
		frame2.grid(column=0, row=7, sticky='nsew')
		frame2.columnconfigure((0,1), weight=1, uniform='group0')

		self.inputVars['screenshotImagePath'] = customtkinter.StringVar(value='')
		self.components['selectScreenshot'] = ImageFilePickerComponent(frame2, 'Select a screenshot image (400x200)', self.inputVars['screenshotImagePath'], self.dataManager.basePath, 'screenshot picker', (400, 200), self.customColors['grayButton'])
		self.components['selectScreenshot'].grid(column=0, row=0, padx=20, pady=(0,0), sticky='nw', rowspan=2)

		self.inputVars['thumbnailImagePath'] = customtkinter.StringVar(value='')
		self.components['selectThumbnail'] = ImageFilePickerComponent(frame2, 'Select a tumbnail image (64x64)', self.inputVars['thumbnailImagePath'], self.dataManager.basePath, 'tumbnail picker', (64, 64), self.customColors['grayButton'])
		self.components['selectThumbnail'].grid(column=1, row=0, padx=20, pady=(0,10), sticky='nw')

		# ---
		self.components['sep2'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep2'].grid(column=0, row=8, padx=20, pady=5, sticky='ew')

		# path select
		frame3 = self.components['frame3'] = customtkinter.CTkFrame(master=self.currentMainFrame, fg_color='transparent')
		frame3.grid(column=0, row=9, sticky='nsew')
		frame3.columnconfigure((0,1), weight=1, uniform='group0')

		self.inputVars['assetFolderPath'] = customtkinter.StringVar(value='')
		self.components['selectAssetDir'] = DirectoryPickerComponent(frame3, 'Select a Folder containing the uassets to pack* \n(this folder should have been taken/selected\ndirectly from the Content folder of your project)', self.inputVars['assetFolderPath'], self.dataManager.basePath, 'asset folder picker', self.customColors['grayButton'])
		self.components['selectAssetDir'].grid(column=0, row=0, padx=20, pady=(0,10), sticky='nw')

		self.inputVars['outputFolderPath'] = customtkinter.StringVar(value='')
		self.components['selectOutputDir'] = DirectoryPickerComponent(frame3, '\n\nSelect an output Folder*', self.inputVars['outputFolderPath'], self.dataManager.basePath, 'output folder', self.customColors['grayButton'])
		self.components['selectOutputDir'].grid(column=1, row=0, padx=20, pady=(0,10), sticky='nw')
		
		# ---
		self.components['sep3'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep3'].grid(column=0, row=10, padx=20, pady=5, sticky='ew')

		# bottom buttons
		self.components['actionButtons'] = ButtonRowComponent(self.currentMainFrame, ('cancel', 'confirm'), (self.cancelButtonCB, self.infoInputConfirmCB), (self.customColors['grayButton'], self.customColors['blueButton']))
		self.components['actionButtons'].grid(column=0, row=11 ,padx=20, pady=(0,10), sticky='se')

#-
	def displayFileTypeInput(self) -> None:
		self.resetMainFrame()
		self.geometry('500x800')

		self.currentMainFrame.columnconfigure(0, weight=1)

		self.components['labelTitle'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Addtional Info:', justify='left', font=customtkinter.CTkFont(size=25, weight= 'bold'))
		self.components['labelTitle'].grid(column=0, row=0, padx=20, pady=(15,5), sticky='sw')

		# ---
		self.components['sep0'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep0'].grid(column=0, row=1, padx=20, pady=10, sticky='ew')

		self.components['labelDesc'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Unable to determine the asset types for the following files\nmanualy set types (optional):', justify='left')
		self.components['labelDesc'].grid(column=0, row=2, padx=20, pady=(10,10), sticky='nw')

		# 16 is an estimate an may be subject to change
		if len(self.unknownFiles) >= 16:
			assetListFrame = customtkinter.CTkScrollableFrame(master=self.currentMainFrame)
		else:
			assetListFrame = customtkinter.CTkFrame(master=self.currentMainFrame)

		# layout
		assetListFrame.grid(column=0, row=3, padx=20, pady=(10,0), sticky='nsew')
		assetListFrame.columnconfigure(0, weight=1)
		self.currentMainFrame.rowconfigure(3, weight=1)

		# bottom buttons
		self.components['actionButtons'] = ButtonRowComponent(self.currentMainFrame, ('cancel', 'skip', 'confirm'), (self.cancelButtonCB, self.infoFileTypeInputSkipCB, self.infoFileTypeInputConfirmCB), (self.customColors['grayButton'], self.customColors['grayButton'], self.customColors['blueButton']))
		self.components['actionButtons'].grid(column=0, row=4 ,padx=20, pady=(0,10), sticky='se')

		# prep data
		rowIndex = 0
		assetTypeList = ['other']
		assetTypeList.extend(list(self.dataManager.assetTypeTable.values()))

		for filename in self.unknownFiles:
			self.components[filename] = OptionMenuWithLabel(assetListFrame, filename, assetTypeList, self.customColors['customOptionMenu'])
			self.components[filename].grid(column=0, row=rowIndex, padx=20, pady=(10,0), sticky='ne')
			rowIndex += 1


#-
	def displayExportOptions(self) -> None:
		self.resetMainFrame()
		self.geometry('600x400')

		self.currentMainFrame.columnconfigure(0, weight=1)
		self.currentMainFrame.rowconfigure(6, weight=1)

		self.components['labelTitle'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Export options:', justify='left', font=customtkinter.CTkFont(size=25, weight= 'bold'))
		self.components['labelTitle'].grid(column=0, row=0, padx=20, pady=(15,5), sticky='sw')

		# ---
		self.components['sep0'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep0'].grid(column=0, row=1, padx=20, pady=10, sticky='ew')

		self.components['labelDesc'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Select export options*:', justify='left', font=customtkinter.CTkFont(size=16))
		self.components['labelDesc'].grid(column=0, row=2, padx=20, pady=10, sticky='nw')

		checkboxMargin = 30

		self.components['selectZipped'] = customtkinter.CTkCheckBox(master=self.currentMainFrame, text='Export Zipped pack')
		self.components['selectZipped'].grid(column=0, row=3, padx=(20+checkboxMargin,20), pady=10, sticky='ew')

		self.components['selectUnpacked'] = customtkinter.CTkCheckBox(master=self.currentMainFrame, text='Export full unpacked file structure')
		self.components['selectUnpacked'].grid(column=0, row=4, padx=(20+checkboxMargin,20), pady=10, sticky='ew')

		engineVersion = self.dataManager.UEDir.split('\\')[-1]
		self.components['selectInstall'] = customtkinter.CTkCheckBox(master=self.currentMainFrame, text=f'Install pack to current engine version ({engineVersion})')
		self.components['selectInstall'].grid(column=0, row=5, padx=(20+checkboxMargin,20), pady=10, sticky='ew')

		# bottom buttons
		self.components['actionButtons'] = ButtonRowComponent(self.currentMainFrame, ('cancel', 'export'), (self.cancelButtonCB, self.exportConfirmCB), (self.customColors['grayButton'], self.customColors['blueButton']))
		self.components['actionButtons'].grid(column=0, row=6 ,padx=20, pady=(0,10), sticky='sew')

#-
	def displayPending(self) -> None:
		self.resetMainFrame()
		self.geometry('400x200')
		
		# top label
		self.components['titleLabel'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Exporting', font=customtkinter.CTkFont(size=25))
		self.components['titleLabel'].grid(column=0, row=0, padx=10, pady=10, sticky='new')
		self.currentMainFrame.columnconfigure(0, weight=1)

		# progress bar
		self.components['progressBar'] = customtkinter.CTkProgressBar(self.currentMainFrame, mode='indeterminate')
		self.components['progressBar'].start()
		self.components['progressBar'].grid(column=0, row=1, padx=50, pady=0, sticky='ew')
		self.currentMainFrame.rowconfigure(1, weight=1)

#-
	def displayExportReport(self) -> None:
		self.resetMainFrame()

		self.currentMainFrame.columnconfigure(0, weight=1)

		# get job info
		failedJobTypes = self.dataManager.getFailedJobTypes()
		if failedJobTypes == None:
			noFail = True
			self.geometry('400x200')
		else:
			noFail = False
			windowHeight = 200 + len(failedJobTypes) * 30
			self.geometry(f'400x{windowHeight}')

		# title
		self.components['labelTitle'] = customtkinter.CTkLabel(master=self.currentMainFrame, text='Export report:', justify='left', font=customtkinter.CTkFont(size=18, weight= 'bold'))
		self.components['labelTitle'].grid(column=0, row=0, padx=20, pady=(15,5), sticky='sw')

		# ---
		self.components['sep0'] = separatorComponent(master=self.currentMainFrame)
		self.components['sep0'].grid(column=0, row=1, padx=20, pady=10, sticky='ew')

		frame0 = self.components['frame0'] = customtkinter.CTkFrame(master=self.currentMainFrame, fg_color='transparent')
		frame0.grid(column=0, row=2, sticky='ns')
		self.currentMainFrame.rowconfigure(2, weight=1)
		frame0.columnconfigure((0,1), weight=1)
		frame0.rowconfigure(0, weight=1)

		if noFail:
			icon_check = customtkinter.CTkImage(Image.open(os.path.join(CURRENT_FILE_DIR, './images/icon_checkmark.png')), size=(32,32))
			self.components['statusIcon'] = customtkinter.CTkLabel(master=frame0, text='', image=icon_check)
			self.components['statusIcon'].grid(column=0, row=0, padx=10, pady=0, sticky='')

			self.components['reportTitle'] = customtkinter.CTkLabel(master=frame0, text='Success!', font=customtkinter.CTkFont(size=16))
			self.components['reportTitle'].grid(column=1, row=0, padx=10, pady=0, sticky='')

		else:
			icon_warn = customtkinter.CTkImage(Image.open(os.path.join(CURRENT_FILE_DIR, './images/icon_warn.png')), size=(32,32))
			self.components['statusIcon'] = customtkinter.CTkLabel(master=frame0, text='', image=icon_warn)
			self.components['statusIcon'].grid(column=0, row=0, padx=10, pady=0, sticky='')

			self.components['reportTitle'] = customtkinter.CTkLabel(master=frame0, text='Possible errors encountered performing \nthe following actions:', justify='left', font=customtkinter.CTkFont(size=16))
			self.components['reportTitle'].grid(column=1, row=0, padx=10, pady=(0,10), sticky='')

			rowIndex = 1
			if 'robocopy' in failedJobTypes:
				self.components['reportItemCopy'] = customtkinter.CTkLabel(master=frame0, text='Copying files', justify='left')
				self.components['reportItemCopy'].grid(column=1, row=rowIndex, padx=10, pady=(0,5), sticky='nw')
				rowIndex += 1

			if 'archive' in failedJobTypes:
				self.components['reportItemArchive'] = customtkinter.CTkLabel(master=frame0, text='Zipping files', justify='left')
				self.components['reportItemArchive'].grid(column=1, row=rowIndex, padx=10, pady=(0,5), sticky='nw')
				rowIndex += 1

			if 'unrealpak' in failedJobTypes:
				self.components['reportItemPak'] = customtkinter.CTkLabel(master=frame0, text='Generating .upack file', justify='left')
				self.components['reportItemPak'].grid(column=1, row=rowIndex, padx=10, pady=(0,5), sticky='nw')
				rowIndex += 1

		# bottom buttons
		self.components['actionButtons'] = ButtonRowComponent(self.currentMainFrame, ('view in explorer', 'ok'), (self.dataManager.openOutputDir, self.destroy), (self.customColors['grayButton'], self.customColors['blueButton']))
		self.components['actionButtons'].grid(column=0, row=3 ,padx=40, pady=(0,10), sticky='sew')

#---
# callbacks

	def cancelButtonCB(self) -> None:
		""" Button callback.\n
		Displays previous window content. Exits program if no previous step.
		"""
		try:
			step = self.prevSteps.pop()
			step()
		except:
			# if empty, cleanup and close app
			self.dataManager.cleanup()
			self.destroy()

#-
	def infoInputConfirmCB(self) -> None:
		""" Button callback. """
		missingInfo = self.processInfoInput()
		if missingInfo != None:
			InfoModalWindow(self, 'Missing/Invalid fields:\n-' + '\n-'.join(missingInfo))
		else:
			self.unknownFiles = self.dataManager.InferAssetTypes()
			# display next window content
			self.prevSteps.append(self.displayInfoInput)
			if self.unknownFiles == None:
				# go to confirm
				self.displayExportOptions()
			else:
				# prompt for manual add types
				self.displayFileTypeInput()

#-
	def infoFileTypeInputSkipCB(self) -> None:
		""" Button callback. """
		# go to confirm
		self.prevSteps.append(self.displayFileTypeInput)
		self.displayExportOptions()

#-
	def infoFileTypeInputConfirmCB(self) -> None:
		""" Button callback. """
		# add user def types to currently stored ones
		additionalTypes = set()
		for filename in self.unknownFiles:
			additionalTypes.add(self.components[filename].get())
		self.dataManager.addAssetTypes(additionalTypes)

		# go to confirm
		self.prevSteps.append(self.displayFileTypeInput)
		self.displayExportOptions()

#-
	def exportConfirmCB(self) -> None:
		""" Button callback. """
		exportZip = self.components['selectZipped'].get()
		exportunpacked = self.components['selectUnpacked'].get()
		InstallToEngine = self.components['selectInstall'].get()

		# if none are selected
		if not (exportZip or exportunpacked or InstallToEngine):
			InfoModalWindow(self, 'Must select at least one')
		else:
			self.export(exportZip, exportunpacked, InstallToEngine)

#-
	def exportCompleteCB(self) -> None:
		""" dataManager jobs completion callback. """
		self.dataManager.cleanup()
		self.displayExportReport()

#---
# input validators

	def registerValidators(self) -> None:
		""" Register field validators with tk. """
		self.validateVersion = (self.register(lambda s: self.validateRequiredCB(s, 'inputVersion', 'warnTextVersion')), '%s')
		self.validateName =    (self.register(lambda s: self.validateRequiredCB(s, 'inputName', 'warnTextName')), '%s')

#-
	def validateRequiredCB(self, string, entryName, labelName) -> bool:
		""" Validate Required Field. """
		if not len(string):
			self.components[labelName].configure(True, **{'text':'required'})
			self.components[entryName].configure(True, **self.customColors['badEntry'])
			return False
		else:
			self.components[labelName].configure(True, **{'text':''})
			self.components[entryName].configure(True, **self.customColors['normalEntry'])
			return True

#---
# other

	def processInfoInput(self) -> list | None:
		""" Process all the info from user inputs.\n
		Returns missing info excluding assetTypes, or None if all good.
		"""

		# submit inputs to dataManager
		self.dataManager.setPackInfo(
			packName       = self.components['inputName'].get(),
			version        = self.components['inputVersion'].get(),
			descrition     = self.components['inputDesc'].get('1.0', 'end'),
			category       = self.components['inputCategory'].get(),
			tags           = self.components['inputTags'].get(),
			assetsPath     = self.inputVars['assetFolderPath'].get(),
			tumbnailPath   = self.inputVars['thumbnailImagePath'].get(),
			screenshotPath = self.inputVars['screenshotImagePath'].get(),
			outputPath     = self.inputVars['outputFolderPath'].get()
		)
		# get all missing/invalid inputs
		missingInfo = self.dataManager.getMissingPackInfo()
		# exclude assetTypes
		try:
			missingInfo.remove('packAssetTypes')
			if not len(missingInfo):
				missingInfo = None
		except:
			pass

		if missingInfo == None:
			return None
		else:
			return [item.removeprefix('pack') for item in missingInfo]

#-
	def resetMainFrame(self) -> None:
		""" Reset the main window content. """

		if(self.currentMainFrame != None):
			self.currentMainFrame.destroy()
		# de-ref sub components and clear them from mem
		self.components = {}
		gc.collect()

		# initialize new frame
		self.currentMainFrame = customtkinter.CTkFrame(master=self, fg_color='transparent')
		# outer layout
		self.currentMainFrame.grid(column=0, row=0, padx=0, pady=0, sticky='nsew')
		self.columnconfigure(0, weight=1)
		self.rowconfigure(0, weight=1)

#-
	def export(self, zipped, unpacked, installToEngine) -> None:

		self.displayPending()
		self.dataManager.generateFileData()
		self.dataManager.createPack(zipped, unpacked, installToEngine)
		self.pollDataManagerJobsLoop()

#-
	def pollDataManagerJobsLoop(self) -> None:
		""" Loop for waiting on job completion. """

		activeCount, pendingCount = self.dataManager.pollJobs()
		self.unfinishedJobCount = activeCount + pendingCount

		if self.unfinishedJobCount == 0:
			self.exportCompleteCB()
		else:
			self.after(500, self.pollDataManagerJobsLoop)