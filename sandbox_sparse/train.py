#!/usr/bin/env python

import common.hyperparameters, common.options
HYPERPARAMETERS = common.hyperparameters.read("attardi07_english_ptb")
common.options.reparse(HYPERPARAMETERS)

import common.dump
rundir = common.dump.create_canonical_directory(HYPERPARAMETERS)

import examples
from vocabulary import *
from common.stats import stats
from common.file import myopen
import sys
import numpy as N
import math
from os.path import join
import cPickle
import random

random.seed(HYPERPARAMETERS["random seed"])
N.random.seed(HYPERPARAMETERS["random seed"])

IDIM = featuremap.len
ODIM = labelmap.len
HID = HYPERPARAMETERS["hidden dimensions"]
LR = HYPERPARAMETERS["learning rate"]
HLAYERS = HYPERPARAMETERS["hidden layers"]

from pylearn.algorithms.weights import random_weights
w1 = random_weights(IDIM, HID)
b1 = N.zeros(HID)
if HLAYERS == 2:
    wh = random_weights(HID, HID)
    bh = N.zeros(HID)
w2 = random_weights(HID, ODIM)
b2 = N.zeros(ODIM)

import graph

def abs_prehidden(prehidden, str="Prehidden"):
    abs_prehidden = N.abs(prehidden)
    med = N.median(abs_prehidden)
    abs_prehidden = abs_prehidden.tolist()
    assert len(abs_prehidden) == 1
    abs_prehidden = abs_prehidden[0]
    abs_prehidden.sort()
    abs_prehidden.reverse()
    print >> sys.stderr, cnt, "Abs%s median =" % str, med, "max =", abs_prehidden[:5]

best_validation_accuracy = 0.
best_validation_at = 0
def validate():
    acc = []
    for (i, (x, y)) in enumerate(examples.get_validation_example()):
        if HLAYERS == 2:
            o = graph.validatefn(x, N.array([y]), w1, b1, wh, bh, w2, b2)
            (kl, softmax, argmax, prehidden1, prehidden2) = o
        else:
            o = graph.validatefn(x, N.array([y]), w1, b1, w2, b2)
            (kl, softmax, argmax, prehidden) = o

        if argmax == y: acc.append(1.)
        else: acc.append(0.)

        if i < 5:
            if HLAYERS == 2:
                abs_prehidden(prehidden1, "Prehidden1")
                abs_prehidden(prehidden2, "Prehidden2")
            else:
                abs_prehidden(prehidden)       

    return N.mean(acc), N.std(acc)

def state_save():
    if HLAYERS == 2:
        cPickle.dump((w1, b1, wh, bh, w2, b2), myopen(join(rundir, "best-model.pkl"), "w"), protocol=-1)
    else:
        cPickle.dump((w1, b1, w2, b2), myopen(join(rundir, "best-model.pkl"), "w"), protocol=-1)
    myopen(join(rundir, "best-model-validation.txt"), "w").write("Accuracy %.2f%% after %d updates" % (best_validation_accuracy*100, best_validation_at))

mvgavg_accuracy = 0.
mvgavg_variance = 0.
cnt = 0
for (x, y) in examples.get_training_example():
    cnt += 1
#    print x, y
#    print "Target y =", y
    if HLAYERS == 2:
        o = graph.trainfn(x, N.array([y]), w1, b1, wh, bh, w2, b2)
        (kl, softmax, argmax, prehidden1, prehidden2, gw1, gb1, gwh, gbh, gw2, gb2) = o
    else:
        o = graph.trainfn(x, N.array([y]), w1, b1, w2, b2)
        (kl, softmax, argmax, prehidden, gw1, gb1, gw2, gb2) = o
#    print "old KL=%.3f, softmax=%s, argmax=%d" % (kl, softmax, argmax)
#    print "old KL=%.3f, argmax=%d" % (kl, argmax)

    if argmax == y: this_accuracy = 1.
    else: this_accuracy = 0.
    mvgavg_accuracy = mvgavg_accuracy - (2. / cnt) * (mvgavg_accuracy - this_accuracy)
    # Should I compute mvgavg_variance before updating the mvgavg_accuracy?
    this_variance = (this_accuracy - mvgavg_accuracy) * (this_accuracy - mvgavg_accuracy)
    mvgavg_variance = mvgavg_variance - (2. / cnt) * (mvgavg_variance - this_variance)
#    print "Accuracy (moving average): %.2f%%, stddev: %.2f%%" % (100. * mvgavg_accuracy, 100. * math.sqrt(mvgavg_variance))

    # Only sum the gradient along the non-zeroes.
    # How do we implement this as C code?
    for idx in x.indices:
        w1[idx,:] -= gw1[idx,:] * LR
#     w1 -= gw1 * LR
    b1 -= gb1 * LR
    if HLAYERS == 2:
        wh -= gwh * LR
        bh -= gbh * LR
    w2 -= gw2 * LR
    b2 -= gb2 * LR

#    o = graph.validatefn(x, N.array([y]), w1, b1, w2, b2)
#    (kl, softmax, argmax, presquashh) = o
##    print "new KL=%.3f, softmax=%s, argmax=%d" % (kl, softmax, argmax)
#    print "new KL=%.3f, argmax=%d" % (kl, argmax)

    if cnt % HYPERPARAMETERS["examples per validation"] == 0:
        valacc, valstd = validate()
        sys.stderr.write("After %d training examples, validation accuracy: %.2f%%, stddev: %.2f%% (former best=%.2f%% at %d)\n" % (cnt, valacc*100, valstd*100, best_validation_accuracy*100, best_validation_at))
        if best_validation_accuracy < valacc:
            best_validation_accuracy = valacc
            best_validation_at = cnt
            sys.stderr.write("NEW BEST VALIDATION ACCURACY. Saving state.\n")
            state_save()
        elif cnt > 2*best_validation_at and cnt >= HYPERPARAMETERS["minimum training updates"]:
            sys.stderr.write("Have not beaten best validation accuracy for a while. Terminating training...\n")
            sys.stderr.write(stats() + "\n")
            break
    if cnt % 1000 == 0:
        sys.stderr.write("After %d training examples, training accuracy (moving average): %.2f%%, stddev: %.2f%%\n" % (cnt, 100. * mvgavg_accuracy, 100. * math.sqrt(mvgavg_variance)))
        sys.stderr.write(stats() + "\n")

#graph.COMPILE_MODE.print_summary()
