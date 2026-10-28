"""Offline Random Forest training and ESP32-safe model export (not deployed).

Requires: pip install scikit-learn (desktop ONLY).
CSV columns: run_id,label,f415,f445,f480,f515,f555,f590,
totalFluorescence,ratio590to445,slope415to590

Labeled physical raw seawater samples must come from final optics. Groups are
split by run_id to prevent leakage. One known run is never in both sets.
"""
import argparse
import csv
import json
import pathlib
from collections import Counter

from services.edge_model import FEATURE_KEYS, LABELS, validate_model


def _rows(path):
    with open(path,newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows:
        raise ValueError("Training file is empty")
    if not {"run_id","label",*FEATURE_KEYS}.issubset(rows[0]):
        raise ValueError("CSV missing required columns")
    for row in rows:
        if row["label"] not in LABELS or not row["run_id"]:
            raise ValueError("Invalid class or experiment run ID")
    return rows


def _encode_tree(tree,classes):
    result=[]
    for i in range(tree.node_count):
        if tree.feature[i]<0:
            by_class={str(label):float(value) for label,value in zip(classes,tree.value[i][0])}
            probs=[by_class.get(k,0.0) for k in LABELS]
            result.append([-1,probs,0,0])
        else:
            result.append([int(tree.feature[i]),float(tree.threshold[i]),
                           int(tree.children_left[i]),int(tree.children_right[i])])
    return result


def train(csv_path,output_dir,version,threshold=0.8):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report,confusion_matrix
    from sklearn.model_selection import GroupShuffleSplit
    rows=_rows(csv_path)
    groups=[r["run_id"] for r in rows]
    if len(set(groups))<15 or set(r["label"] for r in rows)!=set(LABELS):
        raise ValueError("Require at least 15 independent labeled runs across all three classes")
    X=[[float(r[k]) for k in FEATURE_KEYS] for r in rows]
    y=[r["label"] for r in rows]
    first=GroupShuffleSplit(n_splits=1,test_size=0.20,random_state=42)
    train_val_idx,test_idx=next(first.split(X,y,groups))
    # Split validation at experiment-run level from train_val set.
    second=GroupShuffleSplit(n_splits=1,test_size=0.25,random_state=17)
    a,b=next(second.split([X[i] for i in train_val_idx],
                          [y[i] for i in train_val_idx],
                          [groups[i] for i in train_val_idx]))
    train_idx=[train_val_idx[i] for i in a]
    val_idx=[train_val_idx[i] for i in b]
    for name,indices in [("train",train_idx),("validation",val_idx),("test",test_idx)]:
        if not set(LABELS).issubset({y[i] for i in indices}):
            raise ValueError("Each split must contain every class; collect more independent runs")
    classifier=RandomForestClassifier(n_estimators=32,max_depth=6,
                                      min_samples_leaf=2,random_state=137,
                                      class_weight="balanced")
    classifier.fit([X[i] for i in train_idx],[y[i] for i in train_idx])
    output=pathlib.Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    model={"schema":1,"version":version,"features":list(FEATURE_KEYS),
           "classes":list(LABELS),"minConfidence":threshold,
           "trees":[_encode_tree(est.tree_,classifier.classes_)
                    for est in classifier.estimators_]}
    validate_model(model)
    report={"source":"PHYSICAL_EXPERIMENTAL_DATA_REQUIRED",
            "version":version,"count":len(rows),
            "groupCount":len(set(groups)),
            "classes":dict(Counter(y))}
    for name,idx in (("validation",val_idx),("test",test_idx)):
        expected=[y[i] for i in idx]
        predicted=classifier.predict([X[i] for i in idx]).tolist()
        probabilities=classifier.predict_proba([X[i] for i in idx])
        # Post-threshold abstention is mandatory; evaluate false alerts.
        choices=[label if max(p)>=threshold else "INCONCLUSIVE"
                 for label,p in zip(predicted,probabilities)]
        report[name]={"sampleCount":len(idx),
                      "groups":sorted(set(groups[i] for i in idx)),
                      "confusionMatrix":confusion_matrix(expected,choices,
                                labels=list(LABELS)+["INCONCLUSIVE"]).tolist(),
                      "classificationReport":classification_report(
                          expected,choices,labels=list(LABELS)+["INCONCLUSIVE"],
                          output_dict=True,zero_division=0),
                      "petroleumFalseAlerts":sum(
                          y[i]!="PETROLEUM" and label=="PETROLEUM"
                          for i,label in zip(idx,choices))}
    (output/"edge-model.json").write_text(json.dumps(model,separators=(",",":")))
    (output/"evaluation.json").write_text(json.dumps(report,indent=2))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--version",required=True)
    parser.add_argument("--threshold",type=float,default=0.8)
    args=parser.parse_args()
    print(json.dumps(train(args.dataset,args.output,args.version,args.threshold),indent=2))


if __name__=="__main__":
    main()
