import json

import mlflow
import tempfile
import os
import wandb
import hydra
from omegaconf import DictConfig

_steps = [
    "download",
    "basic_cleaning",
    "data_check",
    "data_split",
    "train_random_forest",
    # NOTE: We do not include this in the steps so it is not run by mistake.
    # You first need to promote a model export to "prod" before you can run this,
    # then you need to run this step explicitly
#    "test_regression_model"
]


# This automatically reads in the configuration
@hydra.main(config_name='config')
def go(config: DictConfig):

    # Setup the wandb experiment. All runs will be grouped under this name
    os.environ["WANDB_PROJECT"] = config["main"]["project_name"]
    os.environ["WANDB_RUN_GROUP"] = config["main"]["experiment_name"]

    # Steps to execute
    steps_par = config['main']['steps']
    active_steps = steps_par.split(",") if steps_par != "all" else _steps

    # Move to a temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:

        if "download" in active_steps:
            # Download file and load in W&B
            _ = mlflow.run(
                f"{config['main']['components_repository']}/get_data",
                "main",
                version='main',
                env_manager="conda",
                parameters={
                    "sample": config["etl"]["sample"],
                    "artifact_name": "sample.csv",
                    "artifact_type": "raw_data",
                    "artifact_description": "Raw file as downloaded"
                },
            )

        if "basic_cleaning" in active_steps:
            _ = mlflow.run(
                f"{config['main']['model_repository']}/basic_cleaning", 
                "main", 
                version='main', 
                env_manager='conda', 
                parameters={
                    "input_artifact": config["etl"]["sample_dataset"], 
                    "output_artifact": config["etl"]["cleaning_output_dataset"], 
                    "output_type": config["etl"]["cleaning_output_type"], 
                    "output_description": config["etl"]["cleaning_output_description"], 
                    "min_price": config["etl"]["min_price"], 
                    "max_price": config["etl"]["max_price"]
                }
            )

        if "data_check" in active_steps:
            _ = mlflow.run(
                f"{config['main']['model_repository']}/data_check", 
                "main", 
                version="main", 
                env_manager='conda', 
                parameters={
                    "csv": config["data_check"]["csv"], 
                    "ref": config["data_check"]["ref"], 
                    "kl_threshold": config["data_check"]["kl_threshold"], 
                    "min_price": config["data_check"]["min_price"], 
                    "max_price": config["data_check"]["max_price"], 
                    "min_size": config["data_check"]["min_size"], 
                    "max_size": config["data_check"]["max_size"]
                }
            )

        if "data_split" in active_steps:
            _ = mlflow.run(
                f"{config['main']['components_repository']}/train_val_test_split",
                "main",
                version='main',
                env_manager="conda",
                parameters={
                    "input": config["modeling"]["input"], 
                    "test_size": config["modeling"]["test_size"], 
                    "random_seed": config["modeling"]["random_seed"], 
                    "stratify_by": config["modeling"]["stratify_by"]
                }
            )

        if "train_random_forest" in active_steps:

            # NOTE: we need to serialize the random forest configuration into JSON
            rf_config = os.path.abspath("rf_config.json")
            with open(rf_config, "w+") as fp:
                json.dump(dict(config["modeling"]["random_forest"].items()), fp)  # DO NOT TOUCH

            # NOTE: use the rf_config we just created as the rf_config parameter for the train_random_forest
            # step
            _ = mlflow.run(
                f"{config['main']['model_repository']}/train_random_forest", 
                "main", 
                version="main", 
                env_manager='conda', 
                parameters={
                    "trainval_artifact": config["modeling"]["trainval_artifact"], 
                    "val_size": config["modeling"]["val_size"], 
                    "random_seed": config["modeling"]["random_seed"], 
                    "stratify_by": config["modeling"]["stratify_by"], 
                    "rf_config": rf_config, 
                    "max_tfidf_features": config["modeling"]["max_tfidf_features"], 
                    "output_artifact": config["modeling"]["training_output_artifact"]
                }
            )

        if "test_regression_model" in active_steps:

            _ = mlflow.run(
                f"{config['main']['components_repository']}/test_regression_model",
                "main",
                version='main',
                env_manager="conda",
                parameters={
                    "mlflow_model": config["modeling"]["prod_model_artifact"], 
                    "test_dataset": config["modeling"]["test_artifact"]
                }
            )


if __name__ == "__main__":
    go()
