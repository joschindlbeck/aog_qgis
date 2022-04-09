# -*- coding: utf-8 -*-

"""
   09.04.22, joschindlbeck
   This script transforms a vector layer in QGIS to a AGOpenGPS compatible section file;
   it takes a vector layer with quadrats and creans an AGOpenGPS section file where all
   quadrats have already been applied in AGO

"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterCrs,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterMapLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterColor,
                       QgsCoordinateReferenceSystem,
                       QgsProcessingUtils,
                       QgsCoordinateReferenceSystem,
                       QgsProject)
from qgis import processing
from math import cos
from qgis.PyQt.QtGui import QColor


class AgSectionFileCreator(QgsProcessingAlgorithm):
    """
    This is an algorithm that takes a vector layer with quadrats and
    creates an AGOpenGPS Section file in a way that all quadrats are already
    applied in AGO.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_FIELD_BOUNDARY = 'Feldgrenze'
    INPUT_GRID_SMALL = 'Gitterfein'
    INPUT_GRID_LARGE = 'Gittergrob'
    INPUT_WEED_LAYER = 'Unkrautflchen'
    INPUT_COLOR = 'Color'
    INPUT_GRID_CRS = 'GridCrs'
    OUTPUT_SECTIONS_LAYER = 'Sections_joined'  

    INPUT = 'INPUT'
    OUTPUT_SECTION_FILE = 'OUTPUT_SECTION_FILE'
    INPUT_FIELDS_FILE = 'INPUT_FIELDS_FILE'

    mPerDegreeLat = 0.0
    mPerDegreeLon = 0.0
    latStart = 48.9636327590282  # default start latitude
    lonStart = 12.1934211840036  # default start longitude
    count = 0

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return AgSectionFileCreator()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'agsectionfilecreator'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Section file creator for AGOpenGPS')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('AGOpenGPS')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'agopengps'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        helptext = '''
        Create Section file for AGOpenGPS, v2<br>
        <p>09.04.2022, joschindlbeck</p>
        <a href=https://github.com/joschindlbeck/aog_qgis>Github</a>
        Expected Input:
        <b>Field Boundary</b>: Vector Layer with a polygon representing the field boundary. A vector layer generated from Field.kml from AGOOpenGPS works best
        <b>Layer with weeds</b>: Vector Layer with multiple polygons representing the weed spots that shall be applied in AGOpenGPS; the script will mark all other areas within the field boundaries as already applied
        <b>Grid size small / large</b>: To fill the applied areas, the script will generate a grid / quadrats of two different sizes; the size can be entered, however the large size must be a multiple of the small size
        <b>Grid CRS</b>: For the grid calculation, we need a non geographic CRS
        <b>AOG Fields file</b>: Path to the AOG Fields.txt file; this is needed to get the base coordinates that AOG uses internally
        <b>Applied Sections Color</b>: The color to be used for the section patches in AOG that are already applied
        <b>Sections Layer</b>: This is the output layer of the script operation and represents the already applied area for AOG
        <b>Sections.txt file output</b>: Path to the AOG sections file that will be written
        '''
        
        return helptext

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        # -- Input
        # Vector layer with field boundary polygon
        self.addParameter(QgsProcessingParameterMapLayer(self.INPUT_FIELD_BOUNDARY, self.tr(
            'Field Boundary'), defaultValue=None, types=[QgsProcessing.TypeVectorPolygon]))
        # Vector layer with weed polygons
        self.addParameter(QgsProcessingParameterMapLayer(self.INPUT_WEED_LAYER, self.tr(
            'Layer with weeds'), defaultValue=None, types=[QgsProcessing.TypeVectorPolygon]))
        # Crs for grids
        self.addParameter(QgsProcessingParameterCrs(self.INPUT_GRID_CRS, self.tr('Grid CRS'), defaultValue='ProjectCrs'))
        # Size of grids
        self.addParameter(QgsProcessingParameterNumber(self.INPUT_GRID_SMALL, self.tr(
            'Size for small grid'), type=QgsProcessingParameterNumber.Double, defaultValue=1))
        self.addParameter(QgsProcessingParameterNumber(self.INPUT_GRID_LARGE, self.tr(
            'Size for large grid'), type=QgsProcessingParameterNumber.Double, defaultValue=10))
        # Input File Fields.txt from AGOpenGPS for
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT_FIELDS_FILE, self.tr('AOG Fields file')))
        # Color
        self.addParameter(QgsProcessingParameterColor(self.INPUT_COLOR, self.tr("Applied Sections Color"), defaultValue=QColor(27,151,160)))

        # -- Output
        # Output layer for generated sections
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_SECTIONS_LAYER, self.tr(
            'Sections Layer'), type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='TEMPORARY_OUTPUT'))
        # Output File destination for Section.txt
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_SECTION_FILE, "Section.txt file output for AOG"))

    def processAlgorithm(self, parameters, context, model_feedback):
        """
        Here is where the processing itself takes place.
        """
        feedback = QgsProcessingMultiStepFeedback(8, model_feedback)
        results = {}
        outputs = {}

        # -- Temporary outputs
        OUT_LARGE_GRID = 'GrobesGitterErzeugen'
        OUT_SMALL_GRID = 'FeinesGitterErzeugen'
        OUT_AREA_WO_WEEDS = 'UnkrautfreieFlcheErzeugen'
        OUT_EXT_FIELD_BOUNDARY = 'FeldgrenzeExtrahieren'
        OUT_EXT_SMALL_GRID = 'ExtrahiereFeinesGitter'
        OUT_EXT_LARGE_GRID = 'ExtrahiereGrobeGitter'
        OUT_DIFF_LARGE_SMALL_SECT = 'DifferenzAusSectionsGrobUndFein'

        # -- Step 0: Checks
        # is grid small a multiple of grid large?
        grid_small = self.parameterAsDouble(parameters, self.INPUT_GRID_SMALL, context)
        grid_large = self.parameterAsDouble(parameters, self.INPUT_GRID_LARGE, context)
        if grid_large % grid_small != 0:
            # not a multiple
            raise QgsProcessingException("Size of grid small must be a multiple of the size of grid large!")
        
        # Check CRS
        crs: QgsCoordinateReferenceSystem = self.parameterAsCrs(parameters, self.INPUT_GRID_CRS, context)
        if crs.isGeographic():
            # we must use a projected CRS for grid calculation!
            raise QgsProcessingException("Geographic CRS for Grid not allowed! Must be a projected one")


        # -- Step 1: Create large grid within field boundary
        alg_params = {
            'CRS': 'ProjectCrs',
            'EXTENT': parameters[self.INPUT_FIELD_BOUNDARY],
            'HOVERLAY': 0,
            'HSPACING': parameters[self.INPUT_GRID_LARGE],
            'TYPE': 2,  # Rechteck (Polygon)
            'VOVERLAY': 0,
            'VSPACING': parameters[self.INPUT_GRID_LARGE],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_LARGE_GRID] = processing.run('native:creategrid', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # -- Step 2: Create area without wees as difference between Layer weeds and field boundaries
        alg_params = {
            'INPUT': parameters[self.INPUT_FIELD_BOUNDARY],
            'OVERLAY': parameters[self.INPUT_WEED_LAYER],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_AREA_WO_WEEDS] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # -- Step 3: Create small grid within field boundary
        alg_params = {
            'CRS': 'ProjectCrs',
            'EXTENT': parameters[self.INPUT_FIELD_BOUNDARY],
            'HOVERLAY': 0,
            'HSPACING': parameters[self.INPUT_GRID_SMALL],
            'TYPE': 2,  # Rechteck (Polygon)
            'VOVERLAY': 0,
            'VSPACING': parameters[self.INPUT_GRID_SMALL],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_SMALL_GRID] = processing.run('native:creategrid', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # -- Step 4: Extract field boundaries
        alg_params = {
            'INPUT': outputs[OUT_SMALL_GRID]['OUTPUT'],
            'INTERSECT': parameters[self.INPUT_FIELD_BOUNDARY],
            'PREDICATE': [5],  # überlappt
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_EXT_FIELD_BOUNDARY] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # -- Step 5: Extract small grid
        alg_params = {
            'INPUT': outputs[OUT_SMALL_GRID]['OUTPUT'],
            'INTERSECT': outputs[OUT_AREA_WO_WEEDS]['OUTPUT'],
            'PREDICATE': [6],  # sind innerhalb
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_EXT_SMALL_GRID] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # -- Step 6: Extract large grid
        alg_params = {
            'INPUT': outputs[OUT_LARGE_GRID]['OUTPUT'],
            'INTERSECT': outputs[OUT_AREA_WO_WEEDS]['OUTPUT'],
            'PREDICATE': [6],  # sind innerhalb
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_EXT_LARGE_GRID] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # -- Step 7: Difference between Sections large and small
        alg_params = {
            'INPUT': outputs[OUT_EXT_SMALL_GRID]['OUTPUT'],
            'OVERLAY': outputs[OUT_EXT_LARGE_GRID]['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs[OUT_DIFF_LARGE_SMALL_SECT] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # -- Step 8: Merge sections large, small and those on field boundary
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
            'LAYERS': [outputs[OUT_EXT_LARGE_GRID]['OUTPUT'],outputs[OUT_DIFF_LARGE_SMALL_SECT]['OUTPUT'],outputs[OUT_EXT_FIELD_BOUNDARY]['OUTPUT']],
            'OUTPUT': parameters[self.OUTPUT_SECTIONS_LAYER]
        }
        outputs[self.OUTPUT_SECTIONS_LAYER] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results[self.OUTPUT_SECTIONS_LAYER] = outputs[self.OUTPUT_SECTIONS_LAYER]['OUTPUT']

        #-- call processing with child_algorithm = False to immediately get the result vector (key "OUTPUT" of resulting dictionary)
        #sectionsVectorLayer = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=False)['OUTPUT']
        
        # Set Sections layer to result of processing
        #results[self.OUTPUT_SECTIONS_LAYER] = sectionsVectorLayer.dataProvider().dataSourceUri() #sectionsVectorLayer.name()
        
        # -- Step 9: Export to Sections.txt
        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Load Sections Vector Layer
        layerpath = outputs[self.OUTPUT_SECTIONS_LAYER]['OUTPUT']
        sectionsVectorLayer = QgsProcessingUtils.mapLayerFromString(layerpath, context)

        # Retrieve AGO fields file
        fields = self.parameterAsFile(
            parameters, self.INPUT_FIELDS_FILE, context)
        if fields is None:
            raise QgsProcessingException(self.invalidSourceError(
                parameters, self.INPUT_FIELDS_FILE))

        file = self.parameterAsFileOutput(
            parameters, self.OUTPUT_SECTION_FILE, context)

        color: QColor = self.parameterAsColor(parameters, self.INPUT_COLOR, context)
        #feedback.pushInfo('Applied section color is {}'.format(color.green()))

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if file is None:
            raise QgsProcessingException(self.invalidSinkError(
                parameters, self.OUTPUT_SECTION_FILE))

        # Send some information to the user
        #feedback.pushInfo('CRS is {}'.format(source.sourceCrs().authid()))

        # Compute the number of steps to display within the progress bar and
        # get features fromsource 
        total = 100.0 / sectionsVectorLayer.featureCount() if sectionsVectorLayer.featureCount() else 0       

        # Init AGO Logic
        self.setLatLonStart(fields, feedback)
        self.setLocalMetersPerDegree(self.latStart)

        '''
        feedback.pushInfo("Reading Geometries...")
        vertexList = []
        for current, feature in enumerate(features):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                #break
                exit()

            # Get feature geometry
            if feature.hasGeometry():
                # TODO: Fehler wenn kein Qudarat/Rechteck!
                vertices = list(feature.geometry().vertices())
                vertexList.append(self.convertWGS84ToLocal(vertices[0].y(), vertices[0].x()))
                vertexList.append(self.convertWGS84ToLocal(vertices[3].y(), vertices[3].x()))
                vertexList.append(self.convertWGS84ToLocal(vertices[1].y(), vertices[1].x()))
                vertexList.append(self.convertWGS84ToLocal(vertices[2].y(), vertices[2].x()))
            
        # Remove duplicate vertices and split to patches
        # -> when printing two adjacent quadrats, the 2nd vertex of the first is identical to the 1st vertex of the second
        # -> and the 4th vertex of the first is identical to the 3rd of the second
        # 1--2 1--2 1--2
        # |  | |  | |  |
        # 3--4 3--4 3--4
        # => we want to remove the duplicates
        cleanVertexList = []
        patchList = []
        for i, vertex in enumerate(vertexList):
            if i < 4: # we take the first 4
                cleanVertexList.append(vertex)
            else: # checks start with the 5th vertex
                if i % 2: # we check only uneven indexes (5th, 7th, etc.)
                    if not vertex == vertexList[i-3]:
                        # not identical: store this as new patch
                        feedback.pushInfo(str(cleanVertexList))
                        feedback.pushInfo("----------------------")
                        patchList.append(cleanVertexList)
                        # Clear list
                        cleanVertexList.clear()
                        cleanVertexList.append(vertex)
                else: # even index, we use these
                    cleanVertexList.append(vertex)
        

        feedback.pushInfo("Writing Sections file...")
        with open(file, "w") as output_file:
            for patch in patchList:
                output_file.write(str(len(patch))+"\n")
                output_file.write('27,151,160' +"\n")
                for p in patch:
                    output_file.write(p +"\n")

        '''

        feedback.pushInfo("Writing Sections file...")
        # get features to process from sections vector layer
        features = sectionsVectorLayer.getFeatures()
        with open(file, "w") as output_file:
            for current, feature in enumerate(features):
                # Stop the algorithm if cancel button has been clicked
                if feedback.isCanceled():
                    # break
                    exit()

                # Get feature geometry
                if feature.hasGeometry():

                    verticeList = list(feature.geometry().vertices())
                    output_file.write('5' + "\n")
                    output_file.write('{r},{g},{b}'.format(r=color.red(), g=color.green(), b=color.blue()) + "\n")
                    #output_file.write('27,151,160' + "\n")

                    s = self.convertWGS84ToLocal(
                        verticeList[0].y(), verticeList[0].x())
                    output_file.write(s + "\n")
                    self.count = self.count + 1

                    s = self.convertWGS84ToLocal(
                        verticeList[3].y(), verticeList[3].x())
                    output_file.write(s + "\n")
                    self.count = self.count + 1

                    s = self.convertWGS84ToLocal(
                        verticeList[1].y(), verticeList[1].x())
                    output_file.write(s + "\n")
                    self.count = self.count + 1

                    s = self.convertWGS84ToLocal(
                        verticeList[2].y(), verticeList[2].x())
                    output_file.write(s + "\n")
                    self.count = self.count + 1

                # Update the progress bar
                feedback.setProgress(int(current * total))

        # add Section file output to results
        results[self.OUTPUT_SECTION_FILE] = file
        # return results
        return results

    '''
    Opens AOG fields file and reads Start Lat/Lon
    '''

    def setLatLonStart(self, pathToFieldsFile, feedback):
        # read file
        with open(pathToFieldsFile, "r") as field:
            lines = field.readlines()
        # Search StartFix line
        i = lines.index("StartFix\n")
        # get value
        startfix = lines[i+1]
        feedback.pushInfo(f"StartFix from Fields:{startfix}")
        # set latStart and lonStart
        latlon = startfix.split(",")
        self.latStart = float(latlon[0])
        self.lonStart = float(latlon[1])
        feedback.pushInfo(
            f"LatStart is {self.latStart} and LonStart is {self.lonStart}")

    def setLocalMetersPerDegree(self, latStart):
        self.mPerDegreeLat = 111132.92 - 559.82 * cos(2.0 * latStart * 0.01745329251994329576923690766743) + 1.175 * cos(
            4.0 * latStart * 0.01745329251994329576923690766743) - 0.0023 * cos(6.0 * latStart * 0.01745329251994329576923690766743)

        self.mPerDegreeLon = 111412.84 * cos(latStart * 0.01745329251994329576923690766743) - 93.5 * cos(
            3.0 * latStart * 0.01745329251994329576923690766743) + 0.118 * cos(5.0 * latStart * 0.01745329251994329576923690766743)

    def convertWGS84ToLocal(self, Lat, Lon) -> str:

        self.mPerDegreeLon = 111412.84 * \
            cos(Lat * 0.01745329251994329576923690766743) - 93.5 * \
            cos(3.0 * Lat * 0.01745329251994329576923690766743)
        + 0.118 * cos(5.0 * Lat * 0.01745329251994329576923690766743)

        Northing = (Lat - self.latStart) * self.mPerDegreeLat
        Easting = (Lon - self.lonStart) * self.mPerDegreeLon

        return(str(round(Easting, 3)) + "," + str(round(Northing, 3)) + ",0")
