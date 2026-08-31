from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .modeling import evaluate_predictions, fit_model


@dataclass(frozen=True)
class PurgedFold:
    fold:int; train_start:int; train_end:int; test_start:int; test_end:int; purge_rows:int
    @property
    def train_rows(self)->int: return self.train_end-self.train_start
    @property
    def test_rows(self)->int: return self.test_end-self.test_start


def purged_walk_forward_splits(row_count:int,splits:int=3,purge:int=1,minimum_train_rows:int=30,minimum_test_rows:int=5)->list[PurgedFold]:
    if splits<1: raise ValueError("splits must be at least 1")
    if purge<0: raise ValueError("purge must be non-negative")
    if row_count<minimum_train_rows+purge+minimum_test_rows: raise ValueError("Not enough rows for purged walk-forward validation")
    fold_size=max(row_count//(splits+1),minimum_test_rows); folds=[]
    for fold_index in range(splits):
        train_end=fold_size*(fold_index+1); test_start=train_end+purge; test_end=min(test_start+fold_size,row_count)
        if train_end<minimum_train_rows or test_end-test_start<minimum_test_rows: continue
        folds.append(PurgedFold(fold_index+1,0,train_end,test_start,test_end,purge))
    if not folds: raise ValueError("Unable to construct a valid purged walk-forward split")
    return folds


def walk_forward_scores(feature_frame: pd.DataFrame,splits:int=3,purge:int=1)->list[dict[str,float]]:
    folds=purged_walk_forward_splits(len(feature_frame),splits=splits,purge=purge); scores=[]
    for fold in folds:
        train_frame=feature_frame.iloc[fold.train_start:fold.train_end]; test_frame=feature_frame.iloc[fold.test_start:fold.test_end]
        model=fit_model(train_frame); metrics=evaluate_predictions(test_frame["target_return"],model.predict(test_frame))
        scores.append({"fold":float(fold.fold),"train_rows":float(fold.train_rows),"test_rows":float(fold.test_rows),"purge_rows":float(fold.purge_rows),**metrics})
    return scores
