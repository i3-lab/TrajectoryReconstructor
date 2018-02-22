import os
import unittest
import time
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from functools import partial
#------------------------------------------------------------
#
# Locator
#
class CatheterReconstructor(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "CatheterReconstructor" # TODO make this more human readable by adding spaces
    self.parent.categories = ["IGT"]
    self.parent.dependencies = ["Sequences"]
    self.parent.contributors = ["Longquan Chen(BWH), Junichi Tokuda(BWH)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    Catheter path reconstruction based on tracking data.
    """
    self.parent.acknowledgementText = """
    This work is supported by NIH National Center for Image Guided Therapy (P41EB015898).
    """ 
    # replace with organization, grant and thanks.


#------------------------------------------------------------
#
# CatheterReconstructorWidget
#
class CatheterReconstructorWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...

    self.logic = CatheterReconstructorLogic(None)
    self.logic.setWidget(self)
    self.nLocators = 5

    self.sequenceBrowserWidget = slicer.modules.sequencebrowser.widgetRepresentation()
    self.browsingWidget = None
    self.playWidget = None
    self.replayButton = None
    self.recordButton = None
    self.synchonizedNodesWidget = None
    self.sequenceNodeComboBox = None
    self.addSequenceNodeButton = None
    self.removeSequenceNodeButton = None
    self.sequenceNodeCellWidget = None
    self.sequenceBrowserSetting = None
    self.recordingSamplingSetting = None
    for child in self.sequenceBrowserWidget.children():
      if child.className() == "ctkCollapsibleButton":
        if child.text == 'Browsing':
          self.browsingWidget = child
          for grandChild in self.browsingWidget.children():
            if grandChild.className() == "qMRMLSequenceBrowserPlayWidget":
              self.playWidget = grandChild
              for grandGrandChild in self.playWidget.children():
                if grandGrandChild.className() == "QPushButton":
                  if grandGrandChild.toolTip == '<p>Play/Pause</p>':
                    self.replayButton = grandGrandChild
                  elif grandGrandChild.toolTip == '<p>Record proxy nodes modifications continuously</p>':
                    self.recordButton = grandGrandChild
        elif child.text == 'Synchronized nodes':
          self.synchonizedNodesWidget = child
          for grandChild in self.synchonizedNodesWidget.children():
            if grandChild.className() == "qMRMLNodeComboBox":
              self.sequenceNodeComboBox = grandChild
            elif grandChild.className() == "QPushButton" and grandChild.toolTip == '<p>Add the selected sequence to the browser.</p>':
              self.addSequenceNodeButton = grandChild
            elif grandChild.className() == "QPushButton" and grandChild.toolTip == '<p>Remove the selected sequence(s) from the browser.</p>':
              self.removeSequenceNodeButton = grandChild
            elif grandChild.className() == "QTableWidget":
              self.sequenceNodeCellWidget = grandChild
        elif child.text == "Advanced":
          self.sequenceBrowserSetting = child
          for grandChild in self.sequenceBrowserSetting.children():
            if grandChild.className() == "QComboBox": # set the recording speed to Maximum
              self.recordingSamplingSetting = grandChild
              break

    #
    #--------------------------------------------------


    #--------------------------------------------------
    # GUI components
    
    #
    # Registration Matrix Selection Area
    #
    selectionCollapsibleButton = ctk.ctkCollapsibleButton()
    selectionCollapsibleButton.text = "Locator ON/OFF"
    self.layout.addWidget(selectionCollapsibleButton)
  
    selectionFormLayout = qt.QFormLayout(selectionCollapsibleButton)
    
    self.transformSelector = []
    self.locatorActiveCheckBox = []
    self.locatorReplayCheckBox = []
    self.sequenceNodesList = []
    self.sequenceBrowserNodesList = []
    for i in range(self.nLocators):
      self.sequenceNodesList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceNode"))
      slicer.mrmlScene.AddNode(self.sequenceNodesList[i])
      self.sequenceBrowserNodesList.append(slicer.mrmlScene.CreateNodeByClass("vtkMRMLSequenceBrowserNode"))
      slicer.mrmlScene.AddNode(self.sequenceBrowserNodesList[i])
      self.transformSelector.append(slicer.qMRMLNodeComboBox())
      selector = self.transformSelector[i]
      selector.nodeTypes = ( ("vtkMRMLLinearTransformNode"), "" )
      selector.selectNodeUponCreation = True
      selector.addEnabled = False
      selector.removeEnabled = False
      selector.noneEnabled = False
      selector.showHidden = False
      selector.showChildNodeTypes = False
      selector.setMRMLScene( slicer.mrmlScene )
      selector.setToolTip( "Establish a connection with the server" )

      self.locatorActiveCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorActiveCheckBox[i]
      checkbox.checked = 0
      checkbox.text = ' '
      checkbox.setToolTip("Activate locator")
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorActive, checkbox))

      transformLayout = qt.QHBoxLayout()
      transformLayout.addWidget(selector)
      transformLayout.addWidget(checkbox)

      self.locatorReplayCheckBox.append(qt.QCheckBox())
      checkbox = self.locatorReplayCheckBox[i]
      checkbox.checked = 0
      checkbox.text = ' '
      checkbox.setToolTip("Replay locator")
      checkbox.connect(qt.SIGNAL("clicked()"), partial(self.onLocatorReplay, checkbox))
      transformLayout.addWidget(checkbox)
      selectionFormLayout.addRow("Locator #%d:" % i, transformLayout)

      #self.connect(checkbox, qt.SIGNAL("clicked()"), partial(self.onLocatorActive, checkbox))
      #checkbox.connect('toggled(bool)', self.onLocatorActive)

    self.initialize()

    #--------------------------------------------------
    # connections
    #

    # Add vertical spacer
    self.layout.addStretch(1)

  def initialize(self):
    for i in range(self.nLocators):
      self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[i])
      self.sequenceNodeComboBox.setCurrentNode(self.sequenceNodesList[i])
      self.addSequenceNodeButton.click()
      self.recordingSamplingSetting.setCurrentIndex(0)
    self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[0])
  def cleanup(self):
    pass


  def onLocatorActive(self, checkbox):
    removeList = {}
    activeIndex = 0
    for i in range(self.nLocators):
      if self.locatorActiveCheckBox[i] == checkbox:
        activeIndex = i
    trackedNode = self.transformSelector[activeIndex].currentNode()
    self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[activeIndex])
    self.sequenceNodeCellWidget.cellWidget(0, 1).setCurrentNode(trackedNode)
    self.sequenceNodeCellWidget.cellWidget(0, 3).setChecked(True)
    if checkbox.checked == True:
      self.recordButton.setChecked(True)
    else:
      self.recordButton.setChecked(False)
    for i in range(self.nLocators):
      tnode = self.transformSelector[i].currentNode()
      if self.locatorActiveCheckBox[i].checked == True:
        if tnode:
          self.transformSelector[i].setEnabled(False)
          self.logic.addLocator(tnode)
          mnodeID = tnode.GetAttribute('Locator')
          removeList[mnodeID] = False
        else:
          self.locatorActiveCheckBox[i].setChecked(False)
          self.transformSelector[i].setEnabled(True)
      else:
        if tnode:
          mnodeID = tnode.GetAttribute('Locator')
          if mnodeID != None and not (mnodeID in removeList):
            removeList[mnodeID] = True
            self.logic.unlinkLocator(tnode)

        self.transformSelector[i].setEnabled(True)

    for k, v in removeList.iteritems():
      if v:
        pass
        #self.logic.removeLocator(k)
      

  def onLocatorReplay(self, checkbox):
    activeIndex = 0
    for i in range(self.nLocators):
      if self.locatorReplayCheckBox[i] == checkbox:
        activeIndex = i
    self.sequenceBrowserWidget.setActiveBrowserNode(self.sequenceBrowserNodesList[activeIndex])
    if checkbox.checked == True:
      self.replayButton.setChecked(True)
    else:
      self.replayButton.setChecked(False)

  def onReload(self, moduleName="CatheterReconstructor"):
    # Generic reload method for any scripted module.
    # ModuleWizard will subsitute correct default moduleName.
    for i in range(self.nLocators):
      if self.sequenceNodesList[i]:
        slicer.mrmlScene.RemoveNode(self.sequenceNodesList[i])
    del self.sequenceNodesList[:]
    for i in range(self.nLocators):
      if self.sequenceBrowserNodesList[i]:
        slicer.mrmlScene.RemoveNode(self.sequenceBrowserNodesList[i])
    del self.sequenceBrowserNodesList[:]
    globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)


  def updateGUI(self):
    # Enable/disable GUI components based on the state machine

    ##if self.logic.connected():
    #if self.logic.active():
    #  self.activeCheckBox.setChecked(True)
    #else:
    #  self.activeCheckBox.setChecked(False)
    #
    ## Enable/disable 'Active' checkbox 
    #if self.connectorSelector.currentNode():
    #  self.activeCheckBox.setEnabled(True)
    #else:
    #  self.activeCheckBox.setEnabled(False)
    pass

class CurveManager():
  def __init__(self):
    try:
      import CurveMaker
    except ImportError:
      return slicer.util.warningDisplay(
        "Error: Could not find extension CurveMaker. Open Slicer Extension Manager and install "
        "CurveMaker.", "Missing Extension")
    self.cmLogic = CurveMaker.CurveMakerLogic()
    self.curveFiducials = None
    self._curveModel = None
    self.opacity = 1
    self.tubeRadius = 1.0
    self.curveName = ""
    self.curveModelName = ""
    self.step = 1
    self.tagEventExternal = None
    self.externalHandler = None

    self.sliceID = "vtkMRMLSliceNodeRed"

    # Slice is aligned to the first point (0) or last point (1)
    self.slicePosition = 0

  def clear(self):
    if self._curveModel:
      slicer.mrmlScene.RemoveNode(self._curveModel.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self._curveModel)
    if self.curveFiducials:
      slicer.mrmlScene.RemoveNode(self.curveFiducials.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self.curveFiducials)
    self.curveFiducials = None
    self._curveModel = None

  def connectModelNode(self, mrmlModelNode):
    if self._curveModel:
      slicer.mrmlScene.RemoveNode(self._curveModel.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self._curveModel)
    self._curveModel = mrmlModelNode

  def connectMarkerNode(self, mrmlMarkerNode):
    if self.curveFiducials:
      slicer.mrmlScene.RemoveNode(self.curveFiducials.GetDisplayNode())
      slicer.mrmlScene.RemoveNode(self.curveFiducials)
    self.curveFiducials = mrmlMarkerNode

  def setName(self, name):
    self.curveName = name
    self.curveModelName = "%s-Model" % (name)

  def setSliceID(self, name):
    # ID is either "vtkMRMLSliceNodeRed", "vtkMRMLSliceNodeYellow", or "vtkMRMLSliceNodeGreen"
    self.sliceID = name

  def setDefaultSlicePositionToFirstPoint(self):
    self.slicePosition = 0

  def setDefaultSlicePositionToLastPoint(self):
    self.slicePosition = 1

  def setModelColor(self, r, g, b):

    self.cmLogic.ModelColor = [r, g, b]

    # Make slice intersetion visible
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.SetColor([r, g, b])

    if self.curveFiducials:
      dnode = self.curveFiducials.GetMarkupsDisplayNode()
      if dnode:
        dnode.SetSelectedColor([r, g, b])

  def setModelOpacity(self, opacity):
    # Make slice intersetion visible
    self.opacity = opacity
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.opacity(opacity)

  def setManagerTubeRadius(self, radius):
    self.tubeRadius = radius

  def setModifiedEventHandler(self, handler=None):

    self.externalHandler = handler

    if self._curveModel:
      self.tagEventExternal = self._curveModel.AddObserver(vtk.vtkCommand.ModifiedEvent, self.externalHandler)
      return self.tagEventExternal
    else:
      return None

  def resetModifiedEventHandle(self):

    if self._curveModel and self.tagEventExternal:
      self._curveModel.RemoveObserver(self.tagEventExternal)

    self.externalHandler = None
    self.tagEventExternal = None

  def onLineSourceUpdated(self, caller=None, event=None):

    self.cmLogic.updateCurve()

    # Make slice intersetion visible
    if self._curveModel:
      dnode = self._curveModel.GetDisplayNode()
      if dnode:
        dnode.SetSliceIntersectionVisibility(1)

  def startEditLine(self, initPoint=None):

    if self.curveFiducials == None:
      self.curveFiducials = slicer.mrmlScene.CreateNodeByClass("vtkMRMLMarkupsFiducialNode")
      self.curveFiducials.SetName(self.curveName)
      slicer.mrmlScene.AddNode(self.curveFiducials)
      dnode = self.curveFiducials.GetMarkupsDisplayNode()
      if dnode:
        dnode.SetSelectedColor(self.cmLogic.ModelColor)
    if initPoint != None:
      self.curveFiducials.AddFiducial(initPoint[0], initPoint[1], initPoint[2])
      self.moveSliceToLine()

    if self._curveModel == None:
      self._curveModel = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelNode")
      self._curveModel.SetName(self.curveModelName)
      self.setModelOpacity(self.opacity)
      slicer.mrmlScene.AddNode(self._curveModel)
      modelDisplayNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelDisplayNode")
      modelDisplayNode.SetColor(self.cmLogic.ModelColor)
      modelDisplayNode.SetOpacity(self.opacity)
      slicer.mrmlScene.AddNode(modelDisplayNode)
      self._curveModel.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())

    # Set exetrnal handler, if it has not been.
    if self.tagEventExternal == None and self.externalHandler:
      self.tagEventExternal = self._curveModel.AddObserver(vtk.vtkCommand.ModifiedEvent, self.externalHandler)

    self.cmLogic.DestinationNode = self._curveModel
    self.cmLogic.SourceNode = self.curveFiducials
    self.cmLogic.SourceNode.SetAttribute('CurveMaker.CurveModel', self.cmLogic.DestinationNode.GetID())
    self.cmLogic.updateCurve()

    self.cmLogic.CurvePoly = vtk.vtkPolyData()  ## For CurveMaker bug
    self.cmLogic.enableAutomaticUpdate(1)
    self.cmLogic.setInterpolationMethod(1)
    self.cmLogic.setTubeRadius(self.tubeRadius)

    self.tagSourceNode = self.cmLogic.SourceNode.AddObserver('ModifiedEvent', self.onLineSourceUpdated)

  def endEditLine(self):

    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SetCurrentInteractionMode(slicer.vtkMRMLInteractionNode.ViewTransform)  ## Turn off

  def clearLine(self):

    if self.curveFiducials:
      self.curveFiducials.RemoveAllMarkups()
      # To trigger the initializaton, when the user clear the trajectory and restart the planning,
      # the last point of the coronal reference line should be added to the trajectory

    self.cmLogic.updateCurve()

    if self._curveModel:
      pdata = self._curveModel.GetPolyData()
      if pdata:
        pdata.Initialize()

  def getLength(self):

    return self.cmLogic.CurveLength

  def getFirstPoint(self, position):

    if self.curveFiducials == None:
      return False
    elif self.curveFiducials.GetNumberOfFiducials() == 0:
      return False
    else:
      self.curveFiducials.GetNthFiducialPosition(0, position)
      return True

  def getLastPoint(self, position):
    if self.curveFiducials == None:
      return False
    else:
      nFiducials = self.curveFiducials.GetNumberOfFiducials()
      if nFiducials == 0:
        return False
      else:
        self.curveFiducials.GetNthFiducialPosition(nFiducials - 1, position)
        return True

  def moveSliceToLine(self):

    viewer = slicer.mrmlScene.GetNodeByID(self.sliceID)

    if viewer == None:
      return

    if self.curveFiducials.GetNumberOfFiducials() == 0:
      return

    if self.slicePosition == 0:
      index = 0
    else:
      index = self.curveFiducials.GetNumberOfFiducials() - 1

    pos = [0.0] * 3
    self.curveFiducials.GetNthFiducialPosition(index, pos)

    if self.sliceID == "vtkMRMLSliceNodeRed":
      viewer.SetOrientationToAxial()
      viewer.SetSliceOffset(pos[2])
    elif self.sliceID == "vtkMRMLSliceNodeYellow":
      viewer.SetOrientationToSagittal()
      viewer.SetSliceOffset(pos[0])
    elif self.sliceID == "vtkMRMLSliceNodeGreen":
      viewer.SetOrientationToCoronal()
      viewer.SetSliceOffset(pos[1])

  def lockLine(self):

    if (self.curveFiducials):
      self.curveFiducials.SetDisplayVisibility(0)

  def unlockLine(self):

    if (self.curveFiducials):
      self.curveFiducials.SetDisplayVisibility(1)


#------------------------------------------------------------
#
# CatheterReconstructorLogic
#
class CatheterReconstructorLogic(ScriptedLoadableModuleLogic):

  def __init__(self, parent):
    ScriptedLoadableModuleLogic.__init__(self, parent)

    self.scene = slicer.mrmlScene
    self.scene.AddObserver(slicer.vtkMRMLScene.NodeRemovedEvent, self.onNodeRemovedEvent)
    self.widget = None

    self.eventTag = {}

    # IGTL Conenctor Node ID
    self.connectorNodeID = ''

    self.count = 0
    
  def setWidget(self, widget):
    self.widget = widget


  def addLocator(self, tnode):
    if tnode:
      if tnode.GetAttribute('Locator') == None:
        needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
        needleModel = self.scene.GetNodeByID(needleModelID)
        needleModel.SetAndObserveTransformNodeID(tnode.GetID())
        tnode.SetAttribute('Locator', needleModelID)

  def unlinkLocator(self, tnode):
    if tnode:
      print 'unlinkLocator(%s)' % tnode.GetID()
      tnode.RemoveAttribute('Locator')
      tnode.RemoveAttribute('TrajectoryModel')
      tnode.RemoveAttribute('TrajectoryFiducial')

  def removeLocator(self, mnodeID):
    if mnodeID:
      print 'removeLocator(%s)' % mnodeID
      mnode = self.scene.GetNodeByID(mnodeID)
      if mnode:
        print 'removing from the scene'
        dnodeID = mnode.GetDisplayNodeID()
        if dnodeID:
          dnode = self.scene.GetNodeByID(dnodeID)
          if dnode:
            self.scene.RemoveNode(dnode)
        self.scene.RemoveNode(mnode)

  def onNewDeviceEvent(self, caller, event, obj=None):

    cnode = self.scene.GetNodeByID(self.connectorNodeID)
    nInNode = cnode.GetNumberOfIncomingMRMLNodes()
    print nInNode
    for i in range (nInNode):
      node = cnode.GetIncomingMRMLNode(i)
      if not node.GetID() in self.eventTag:
        self.eventTag[node.GetID()] = node.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onIncomingNodeModifiedEvent)
        if node.GetNodeTagName() == 'IGTLTrackingDataSplitter':
          n = node.GetNumberOfTransformNodes()
          for id in range (n):
            tnode = node.GetTransformNode(id)
            if tnode and tnode.GetAttribute('Locator') == None:
              print "No Locator"
              needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
              needleModel = self.scene.GetNodeByID(needleModelID)
              needleModel.SetAndObserveTransformNodeID(tnode.GetID())
              needleModel.InvokeEvent(slicer.vtkMRMLTransformableNode.TransformModifiedEvent)
              tnode.SetAttribute('Locator', needleModelID)

  def createNeedleModel(self, node):
    if node and node.GetClassName() == 'vtkMRMLIGTLTrackingDataBundleNode':
      n = node.GetNumberOfTransformNodes()
      print n
      for id in range (n):
        tnode = node.GetTransformNode(id)
        if tnode:
          needleModelID = self.createNeedleModelNode("Needle_%s" % tnode.GetName())
          needleModel = self.scene.GetNodeByID(needleModelID)
          needleModel.SetAndObserveTransformNodeID(tnode.GetID())
          needleModel.InvokeEvent(slicer.vtkMRMLTransformableNode.TransformModifiedEvent)

  def createNeedleTrajBaseOnCurveMaker(self, name):
    curveManager = CurveManager()
    curveManager.setName(name)
    curveManager.setDefaultSlicePositionToFirstPoint()
    curveManager.setModelColor(1.0, 1.0, 0.5)
    return curveManager

  def createNeedleModelNode(self, name):

    locatorModel = self.scene.CreateNodeByClass('vtkMRMLModelNode')
    
    # Cylinder represents the locator stick
    cylinder = vtk.vtkCylinderSource()
    cylinder.SetRadius(1.5)
    cylinder.SetHeight(100)
    cylinder.SetCenter(0, 0, 0)
    cylinder.Update()

    # Rotate cylinder
    tfilter = vtk.vtkTransformPolyDataFilter()
    trans =   vtk.vtkTransform()
    trans.RotateX(90.0)
    trans.Translate(0.0, -50.0, 0.0)
    trans.Update()
    if vtk.VTK_MAJOR_VERSION <= 5:
      tfilter.SetInput(cylinder.GetOutput())
    else:
      tfilter.SetInputConnection(cylinder.GetOutputPort())
    tfilter.SetTransform(trans)
    tfilter.Update()

    # Sphere represents the locator tip
    sphere = vtk.vtkSphereSource()
    sphere.SetRadius(3.0)
    sphere.SetCenter(0, 0, 0)
    sphere.Update()

    apd = vtk.vtkAppendPolyData()

    if vtk.VTK_MAJOR_VERSION <= 5:
      apd.AddInput(sphere.GetOutput())
      apd.AddInput(tfilter.GetOutput())
    else:
      apd.AddInputConnection(sphere.GetOutputPort())
      apd.AddInputConnection(tfilter.GetOutputPort())
    apd.Update()
    
    locatorModel.SetAndObservePolyData(apd.GetOutput());

    self.scene.AddNode(locatorModel)
    locatorModel.SetScene(self.scene)
    locatorModel.SetName(name)
    
    locatorDisp = locatorModel.GetDisplayNodeID()
    if locatorDisp == None:
      locatorDisp = self.scene.CreateNodeByClass('vtkMRMLModelDisplayNode')
      self.scene.AddNode(locatorDisp)
      locatorDisp.SetScene(self.scene)
      locatorModel.SetAndObserveDisplayNodeID(locatorDisp.GetID());
      
    color = [0, 0, 0]
    color[0] = 0.5
    color[1] = 0.5
    color[2] = 1.0
    locatorDisp.SetColor(color)
    
    return locatorModel.GetID()


  def onNodeRemovedEvent(self, caller, event, obj=None):
    delkey = ''
    if obj == None:
      for k in self.eventTag:
        node = self.scene.GetNodeByID(k)
        if node == None:
          delkey = k
          break

    if delkey != '':
      del self.eventTag[delkey]


