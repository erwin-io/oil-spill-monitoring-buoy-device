"""Compact, validated Random Forest inference, no NumPy on ESP32.

The model JSON must be trained from independently grouped physical experiments;
no built-in pretend oil model or default PETROLEUM classification exists.
"""
import math

FEATURE_KEYS=("f415","f445","f480","f515","f555","f590",
              "totalFluorescence","ratio590to445","slope415to590")
LABELS=("NORMAL","PETROLEUM","INTERFERENCE")
MODEL_SCHEMA=1


def flatten(record):
    spec=record["spectral"]
    return [float(spec[k]) for k in FEATURE_KEYS[:6]]+[
        float(record[k]) for k in FEATURE_KEYS[6:]]


def validate_model(model):
    if not isinstance(model,dict) or set(model)!={"schema","version","features","classes","trees","minConfidence"}:
        raise ValueError("Invalid model keys")
    if model["schema"]!=MODEL_SCHEMA or model["features"]!=list(FEATURE_KEYS):
        raise ValueError("Unsupported model schema")
    if model["classes"]!=list(LABELS) or not isinstance(model["version"],str) or not model["version"]:
        raise ValueError("Invalid model metadata")
    threshold=model["minConfidence"]
    if isinstance(threshold,bool) or not isinstance(threshold,(float,int)) or not 0.5<=threshold<=1:
        raise ValueError("Invalid threshold")
    trees=model["trees"]
    if not isinstance(trees,list) or not 1<=len(trees)<=128:
        raise ValueError("Invalid forest size")
    for tree in trees:
        if not isinstance(tree,list) or not 1<=len(tree)<=2048:
            raise ValueError("Invalid decision tree")
        for i,node in enumerate(tree):
            if not isinstance(node,list) or len(node)!=4:
                raise ValueError("Invalid node")
            index,threshold,left,right=node
            if index==-1:
                if not isinstance(threshold,list) or len(threshold)!=3 or any(
                    type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in threshold):
                    raise ValueError("Invalid leaf")
            else:
                if type(index)!=int or not 0<=index<len(FEATURE_KEYS) or type(threshold) not in (int,float) or not math.isfinite(threshold):
                    raise ValueError("Invalid split")
                if any(type(branch)!=int or not i<branch<len(tree) for branch in (left,right)):
                    raise ValueError("Invalid child")
    return model


class Forest:
    def __init__(self,model):
        self.model=validate_model(model)

    def predict(self,record):
        x=flatten(record)
        if any(not math.isfinite(v) for v in x):
            raise ValueError("Non-finite features")
        counts=[0.0,0.0,0.0]
        for tree in self.model["trees"]:
            pos=0
            for _ in range(len(tree)):
                index,threshold,left,right=tree[pos]
                if index==-1:
                    scale=sum(threshold)
                    if scale<=0:
                        raise ValueError("Invalid leaf probability")
                    for i in range(3):
                        counts[i]+=threshold[i]/scale
                    break
                pos=left if x[index]<=threshold else right
            else:
                raise ValueError("Cyclic tree")
        denominator=sum(counts)
        index=max(range(3),key=lambda i:counts[i])
        confidence=counts[index]/denominator
        # Conservative abstention on unvalidated/low-confidence observations.
        decision=LABELS[index] if confidence>=self.model["minConfidence"] else "INCONCLUSIVE"
        return {"classification":decision,"confidence":confidence,
                "modelVersion":self.model["version"]}
