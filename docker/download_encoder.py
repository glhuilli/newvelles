# Using script from @qmaruf
# Avaialble at: https://qmaruf.github.io/2020/01/07/Deploy-TF-Hub-Module-using-tf-serving/

import tensorflow.compat.v1 as tf
tf.disable_v2_behavior() 
import tensorflow_hub as hub


export_dir = "./universal_encoder/00000001"
with tf.Session(graph=tf.Graph()) as sess:
    module = hub.Module("https://tfhub.dev/google/universal-sentence-encoder/1")
    input_params = module.get_input_info_dict()
    sentence_input = tf.placeholder(name='sentence',
        dtype=input_params['sentence'].dtype,
        shape=input_params['sentence'].get_shape())
    sess.run([tf.global_variables_initializer(), tf.tables_initializer()])
    embeddings = module(sentence_input)
    tf.saved_model.simple_save(sess,
        export_dir,
        inputs={'sentence': sentence_input},
        outputs={'embeddings': embeddings}, 
        legacy_init_op=tf.tables_initializer())
