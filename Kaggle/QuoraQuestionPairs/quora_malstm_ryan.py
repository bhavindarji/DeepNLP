import os
from datetime import datetime
import json
from sklearn.model_selection import train_test_split
import numpy as np
import sys

import tensorflow as tf
from tensorflow.python.keras._impl.keras.preprocessing.text import Tokenizer
from tensorflow.python.keras._impl.keras.preprocessing.sequence import pad_sequences
from tensorflow.python.keras._impl.keras.utils.data_utils import get_file

# from tensorflow.python.keras._impl.keras.preprocessing import sequence

from tensorflow.python.keras._impl.keras import layers
from tensorflow.python.keras import backend as K

# from tensorflow.python.keras._impl.keras.layers import Embedding
# from tensorflow.python.keras._impl.keras.layers import Reshape, Flatten, Dropout, Concatenate, dot, add

## 미리 Global 변수를 지정하자. 파일 명, 파일 위치, 디렉토리 등이 있다.

Q1_TRAINING_DATA_FILE = 'q1_train.npy'
Q2_TRAINING_DATA_FILE = 'q2_train.npy'
LABEL_TRAINING_DATA_FILE = 'label_train.npy'
WORD_EMBEDDING_MATRIX_FILE = 'word_embedding_matrix.npy'
NB_WORDS_DATA_FILE = 'nb_words.json'
DATA_PATH = './data/'

## 학습에 필요한 파라메터들에 대해서 지정하는 부분이다.

BATCH_SIZE = 1024
EPOCH = 50
HIDDEN = 50
BUFFER_SIZE = 2048

TEST_SPLIT = 0.1
RNG_SEED = 13371447
EMBEDDING_DIM = 50
MAX_SEQ_LEN = 25

## 데이터를 불러오는 부분이다. 효과적인 데이터 불러오기를 위해, 미리 넘파이 형태로 저장시킨 데이터를 로드한다.

q1_data = np.load(open(DATA_PATH + Q1_TRAINING_DATA_FILE, 'rb'))
q2_data = np.load(open(DATA_PATH + Q2_TRAINING_DATA_FILE, 'rb'))
labels = np.load(open(DATA_PATH + LABEL_TRAINING_DATA_FILE, 'rb'))

## 미리 저장한 임베딩 값을 불러오자
word_embedding_matrix = np.load(open(DATA_PATH+WORD_EMBEDDING_MATRIX_FILE, 'rb'))
with open(DATA_PATH+NB_WORDS_DATA_FILE, 'r') as f:
    nb_words = json.load(f)['nb_words']

## 데이터를 나누어 저장하자. sklearn의 train_test_split을 사용하면 유용하다. 하지만, 쿼라 데이터의 경우는
## 입력이 1개가 아니라 2개이다. 따라서, np.stack을 사용하여 두개를 하나로 쌓은다음 활용하여 분류한다.

X = np.stack((q1_data, q2_data), axis=1) 
y = labels

# X = word_embedding_matrix[X[:50000]]
# y = y[:50000]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SPLIT, random_state=RNG_SEED)
Q1_train = X_train[:,0]
Q2_train = X_train[:,1]
Q1_test = X_test[:,0]
Q2_test = X_test[:,1]

def rearrange(q, sim_q, labels):
    features = {"q": q, "sim_q": sim_q}
    return features, labels

def train_input_fn():
    dataset = tf.data.Dataset.from_tensor_slices((Q1_train, Q2_train, y_train))
    dataset = dataset.shuffle(buffer_size=len(Q1_train))
    dataset = dataset.batch(16)
    dataset = dataset.map(rearrange)
    dataset = dataset.repeat()
    iterator = dataset.make_one_shot_iterator()
    
    return iterator.get_next()

def test_input_fn():
    dataset = tf.data.Dataset.from_tensor_slices((Q1_test, Q2_test, y_test))
    dataset = dataset.shuffle(buffer_size=len(Q1_test))
    dataset = dataset.batch(16)
    dataset = dataset.map(rearrange)
    dataset = dataset.repeat()
    iterator = dataset.make_one_shot_iterator()
    
    return iterator.get_next()

def RNN_attention(features, labels, mode):
    
    TRAIN = mode == tf.estimator.ModeKeys.TRAIN
    EVAL = mode == tf.estimator.ModeKeys.EVAL
    PREDICT = mode == tf.estimator.ModeKeys.PREDICT
    
    labels = tf.reshape(labels, [-1,1])

    # Embedding layer
    # with tf.device('/cpu:0'), tf.name_scope("embedding"):
    #     W = tf.Variable(
    #         tf.random_uniform([nb_words+1, EMBEDDING_DIM], -1.0, 1.0),
    #         name="W")
    #     q1_emb = tf.nn.embedding_lookup(W, features['q'])
    #     q1_emb_expand = tf.expand_dims(q1_emb, -1)

    #     q2_emb = tf.nn.embedding_lookup(W, features['sim_q'])
    #     q2_emb_expand = tf.expand_dims(q2_emb, -1)

    q1 = layers.Embedding(nb_words + 1, 
                 EMBEDDING_DIM, 
                 weights=[word_embedding_matrix], 
                 input_length=MAX_SEQ_LEN, 
                 trainable=False)(features['q'])
    
    q2 = layers.Embedding(nb_words + 1, 
                 EMBEDDING_DIM, 
                 weights=[word_embedding_matrix], 
                 input_length=MAX_SEQ_LEN, 
                 trainable=False)(features['sim_q'])

    with tf.variable_scope('q_bi_lstm'):
        lstm_fw_cell = tf.contrib.rnn.BasicLSTMCell(num_units = 64, activation = tf.nn.tanh)
        lstm_bw_cell = tf.contrib.rnn.BasicLSTMCell(num_units = 64, activation = tf.nn.tanh)
        _, output_states = tf.nn.bidirectional_dynamic_rnn(cell_fw = lstm_fw_cell,
                                                          cell_bw = lstm_bw_cell,
                                                          inputs = q1_emb_expand,
                                                          dtype = tf.float32)

        q_final_state = tf.concat([output_states[0].h, output_states[1].h], axis=1)
        
        
    with tf.variable_scope('sim_bi_lstm'):
        lstm_fw_cell = tf.contrib.rnn.BasicLSTMCell(num_units = 64, activation = tf.nn.tanh)
        lstm_bw_cell = tf.contrib.rnn.BasicLSTMCell(num_units = 64, activation = tf.nn.tanh)
        _, output_states = tf.nn.bidirectional_dynamic_rnn(cell_fw = lstm_fw_cell,
                                                          cell_bw = lstm_bw_cell,
                                                          inputs = q2_emb_expand,
                                                          dtype = tf.float32)
        
        sim_final_state = tf.concat([output_states[0].h, output_states[1].h], axis=1)
        
    with tf.variable_scope('output_layer'):
        #Malstm
        output = K.exp(-K.sum(K.abs(q_final_state -  sim_final_state), axis=1, keepdims=True))
                
    if TRAIN:
            
        global_step = tf.train.get_global_step()
        
        loss = tf.losses.mean_squared_error(labels, output)
#         loss = tf.losses.sigmoid_cross_entropy(multi_class_labels=tf.one_hot(labels, depth=2),
#                                                logits = output
#                                               )
#         tf.summary.scalar('loss', loss)

        train_op = tf.train.AdamOptimizer(1e-4).minimize(loss, global_step)        

        return tf.estimator.EstimatorSpec(mode=mode, train_op=train_op, loss = loss)
    
    elif EVAL:
        loss = tf.losses.mean_squared_error(labels, output)
        pred = tf.nn.sigmoid(output)
        accuracy = tf.metrics.accuracy(labels, tf.round(pred))
        return tf.estimator.EstimatorSpec(mode=mode, loss=loss, eval_metric_ops={'acc': accuracy})
        
    elif PREDICT:
        return tf.estimator.EstimatorSpec(
            mode=mode,
            predictions={
                'prob': cos_sim,
                'q_sem': q_dense_layer,
                'sim_q_sem': sim_q_dense_layer
            }
        )

model_dir = os.path.join(os.getcwd(), "data/checkpoint/")
os.makedirs(model_dir, exist_ok=True)

config_tf = tf.estimator.RunConfig()
config_tf._save_checkpoints_steps = 100
config_tf._save_checkpoints_secs = None
config_tf._keep_checkpoint_max =  2
config_tf._log_step_count_steps = 100

time_start = datetime.now()

# validation_monitor = tf.contrib

print("Experiment started at {}".format(time_start.strftime("%H:%M:%S")))
print(".......................................") 

tf.logging.set_verbosity(tf.logging.INFO)
print(tf.__version__)

train_spec = tf.estimator.TrainSpec(train_input_fn, max_steps=10000)
# eval_spec = tf.estimator.EvalSpec(eval_input_fn, steps=100)

dssm_est = tf.estimator.Estimator(RNN_attention, model_dir=model_dir, config=config_tf)
dssm_est.train(train_input_fn, steps=10000)

time_end = datetime.now()

print(".......................................")
print("Experiment finished at {}".format(time_end.strftime("%H:%M:%S")))
print("")
time_elapsed = time_end - time_start
print("Experiment elapsed time: {} seconds".format(time_elapsed.total_seconds()))