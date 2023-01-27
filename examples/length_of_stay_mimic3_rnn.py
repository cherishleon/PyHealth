from pyhealth.datasets import MIMIC3Dataset
from pyhealth.datasets import split_by_patient, get_dataloader
from pyhealth.models import RNN, Transformer
from pyhealth.tasks import length_of_stay_prediction_mimic3_fn
from pyhealth.trainer import Trainer

# STEP 1: load data
base_dataset = MIMIC3Dataset(
    root="/srv/local/data/physionet.org/files/mimiciii/1.4",
    tables=["DIAGNOSES_ICD", "PROCEDURES_ICD", "PRESCRIPTIONS"],
    code_mapping={"ICD9CM": "CCSCM", "ICD9PROC": "CCSPROC", "NDC": "ATC"},
    dev=False,
    refresh_cache=True,
)
base_dataset.stat()

# STEP 2: set task
sample_dataset = base_dataset.set_task(length_of_stay_prediction_mimic3_fn)
sample_dataset.stat()

train_dataset, val_dataset, test_dataset = split_by_patient(
    sample_dataset, [0.8, 0.1, 0.1]
)
train_dataloader = get_dataloader(train_dataset, batch_size=32, shuffle=True)
val_dataloader = get_dataloader(val_dataset, batch_size=32, shuffle=False)
test_dataloader = get_dataloader(test_dataset, batch_size=32, shuffle=False)

# STEP 3: define modedl
model = Transformer(
    dataset=sample_dataset,
    feature_keys=["conditions", "procedures", "drugs"],
    label_key="label",
    mode="multiclass",
)

# STEP 4: define trainer
trainer = Trainer(model=model)
trainer.train(
    train_dataloader=train_dataloader,
    val_dataloader=val_dataloader,
    epochs=50,
    monitor="accuracy",
)

# STEP 5: evaluate
trainer.evaluate(test_dataloader)
