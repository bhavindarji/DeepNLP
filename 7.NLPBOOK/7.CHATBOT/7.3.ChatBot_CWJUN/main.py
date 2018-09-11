import tensorflow as tf
import model as ml
import data
import numpy as np
import os

from configs import DEFINES

def main(self):
	inputTrainEncOneHot = []
	outputTrainDecOneHot = []
	# Make Vocabulary
	#######################################################################
	dictionary,  vocabularyLength = data.loadVocabulary()
	# print("#######################################################################")
	# print(dictionary)
	# print(vocabularyLength)
	# print("#######################################################################")
	######################################################################

	# Load Data
	#######################################################################
	xTrain, yTrain, xTest, yTest = data.loadData()
	# print("#######################################################################")
	# print(xTrain)
	# print(yTrain)
	# print("#######################################################################")
	######################################################################

	# START END PADDING  (MaxValue 처리)
	#######################################################################
	inputTrainEnc, inputTrainEncLength = data.encProcessing(xTrain, dictionary)
	outputTrainDec, outputTrainDecLength = data.decOutputProcessing(yTrain, dictionary)
	targetTrainDec = data.decTargetProcessing(yTrain, dictionary)
	
	inputTestEnc, inputTestEncLength = data.encProcessing(xTest,dictionary)
	outputTestDec, outputTestDecLength = data.decOutputProcessing(yTest, dictionary)
	targetTrainDec = data.decTargetProcessing(yTrain, dictionary)
	# print("#######################################################################")
	# print(type(inputTrainEnc))
	# print(type(outputTrainDec))
	# print(type(targetTrainDec))
	# print(inputTrainEnc.shape)
	# print(outputTrainDec.shape)
	# print(targetTrainDec.shape)
	# print("#######################################################################")
	#######################################################################	
	# classifier 
	#######################################################################
	# Create a directory to save
	checkPointPath = os.path.join(os.getcwd(), DEFINES.checkPointPath)
	os.makedirs(checkPointPath, exist_ok=True)
	
	classifier = tf.estimator.Estimator(
			model_fn=ml.Model, 
			model_dir=DEFINES.checkPointPath,
			params={
				'hiddenSize': DEFINES.hiddenSize,
				'layerSize': DEFINES.layerSize,
				'learningRate': DEFINES.learningRate,
				'vocabularyLength': vocabularyLength,
				'embeddingSize': DEFINES.embeddingSize,
			})
	#print("#######################################################################")
	print(classifier)
	#print("#######################################################################")	
	######################################################################

	#######################################################################
	classifier.train(input_fn=lambda:data.trainInputFn(
		inputTrainEnc, outputTrainDec, targetTrainDec,  DEFINES.batchSize), steps=DEFINES.trainSteps)
	#######################################################################


	#######################################################################
	evalResult = classifier.evaluate(input_fn=lambda:data.evalInputFn(
		inputTestEnc, outputTestDec, targetTestDec,  DEFINES.batchSize), steps=DEFINES.trainSteps)
	print('\nTest set accuracy: {accuracy:0.3f}\n'.format(**evalResult))
	#######################################################################

	# 결과값 바로 나오도록 처리
	# inputPredicEnc, outputPredicDec
	#idx2char, idx2charLength = data.idx2char(dictionary)
	#print(idx2char)
	#print(idx2charLength)
	# enc = 연애를 잘하는사람들 멋져

	predictions = classifier.predict(
		input_fn=lambda:data.evalInputFn(inputTestEnc, outputTestDec, labels=None, batch_size=DEFINES.batchSize))
													
if __name__ == '__main__':
	tf.logging.set_verbosity(tf.logging.INFO)
	tf.app.run(main)
