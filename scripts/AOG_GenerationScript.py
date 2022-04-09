"""
Model exported as python.
Name : AOG Section aus AG Tracker
Group : AOG
With QGIS : 32002
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterMapLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsCoordinateReferenceSystem
import processing


class AogSectionAusAgTracker(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('Feldgrenze', 'Feldgrenze', defaultValue=None, types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber('Gittergrefein', 'Gittergröße fein', type=QgsProcessingParameterNumber.Double, defaultValue=1))
        self.addParameter(QgsProcessingParameterNumber('Gittergregrob', 'Gittergröße grob', type=QgsProcessingParameterNumber.Double, defaultValue=10))
        self.addParameter(QgsProcessingParameterMapLayer('Unkrautflchen', 'Unkrautflächen', defaultValue=None, types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSink('Sections_joined', 'Sections_joined', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue='TEMPORARY_OUTPUT'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(8, model_feedback)
        results = {}
        outputs = {}

        # Grobes Gitter erzeugen
        alg_params = {
            'CRS': 'ProjectCrs',
            'EXTENT': parameters['Feldgrenze'],
            'HOVERLAY': 0,
            'HSPACING': parameters['Gittergregrob'],
            'TYPE': 2,  # Rechteck (Polygon)
            'VOVERLAY': 0,
            'VSPACING': parameters['Gittergregrob'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['GrobesGitterErzeugen'] = processing.run('native:creategrid', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Unkrautfreie Fläche Erzeugen
        alg_params = {
            'INPUT': parameters['Feldgrenze'],
            'OVERLAY': parameters['Unkrautflchen'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['UnkrautfreieFlcheErzeugen'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Feines Gitter erzeugen
        alg_params = {
            'CRS': 'ProjectCrs',
            'EXTENT': parameters['Feldgrenze'],
            'HOVERLAY': 0,
            'HSPACING': parameters['Gittergrefein'],
            'TYPE': 2,  # Rechteck (Polygon)
            'VOVERLAY': 0,
            'VSPACING': parameters['Gittergrefein'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FeinesGitterErzeugen'] = processing.run('native:creategrid', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Feldgrenze extrahieren
        alg_params = {
            'INPUT': outputs['FeinesGitterErzeugen']['OUTPUT'],
            'INTERSECT': parameters['Feldgrenze'],
            'PREDICATE': [5],  # überlappt
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FeldgrenzeExtrahieren'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Extrahiere feines Gitter
        alg_params = {
            'INPUT': outputs['FeinesGitterErzeugen']['OUTPUT'],
            'INTERSECT': outputs['UnkrautfreieFlcheErzeugen']['OUTPUT'],
            'PREDICATE': [6],  # sind innerhalb
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtrahiereFeinesGitter'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Extrahiere Grobe Gitter
        alg_params = {
            'INPUT': outputs['GrobesGitterErzeugen']['OUTPUT'],
            'INTERSECT': outputs['UnkrautfreieFlcheErzeugen']['OUTPUT'],
            'PREDICATE': [6],  # sind innerhalb
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtrahiereGrobeGitter'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Differenz aus Sections grob und fein
        alg_params = {
            'INPUT': outputs['ExtrahiereFeinesGitter']['OUTPUT'],
            'OVERLAY': outputs['ExtrahiereGrobeGitter']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DifferenzAusSectionsGrobUndFein'] = processing.run('native:difference', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Sections grob, fein und Grenze zusammenführen
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
            'LAYERS': [outputs['ExtrahiereGrobeGitter']['OUTPUT'],outputs['DifferenzAusSectionsGrobUndFein']['OUTPUT'],outputs['FeldgrenzeExtrahieren']['OUTPUT']],
            'OUTPUT': parameters['Sections_joined']
        }
        outputs['SectionsGrobFeinUndGrenzeZusammenfhren'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Sections_joined'] = outputs['SectionsGrobFeinUndGrenzeZusammenfhren']['OUTPUT']
        return results

    def name(self):
        return 'AOG Section aus AG Tracker'

    def displayName(self):
        return 'AOG Section aus AG Tracker'

    def group(self):
        return 'AOG'

    def groupId(self):
        return 'AOG'

    def createInstance(self):
        return AogSectionAusAgTracker()
