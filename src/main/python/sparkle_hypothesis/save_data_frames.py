import inspect
from typing import List, Union, Dict

from hypothesis.internal.reflection import proxies
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, BooleanType, DateType, \
    TimestampType, LongType


def save_dfs(input_as_df: bool = False):
    """
    #:param input_as_df feed your test method with data frames or (default) the original hypothesis data (Dicts)

    Create spark tables for each input dictionary using the argument name as table name and using
    the type embedded in the dictionary keys

    table_strategy = st.fixed_dictionary({"col_1:int": st.just(1)})

    @given(table_strategy)
    @save_dfs()
    def method_a(self, table_1):
        self.spark.table("table_1").show()
        # outputs
        +-----+
        |col_1|
        +-----+
        |    1|
        +-----+
    """

    def save_data_frames(fn):
        @proxies(fn)
        def wrapped(*args, **kwargs):
            spark = args[0].spark
            dict_names = list(inspect.signature(fn).parameters.keys())
            result = [_dicts_to_table(spark, d, dict_names[idx + 1]) for idx, d in enumerate(args[1:])]
            if input_as_df:
                head, *tail = args
                args = [head] + result
            rc = fn(*args, **kwargs)
            return rc

        return wrapped

    return save_data_frames


def rename_keys(d: dict):
    new_dict = {}
    for key in d.keys():  # type: (str, object)
        new_key = key.split(':')[0]
        new_dict[new_key] = d[key]
    d.clear()
    d.update(new_dict)


def _dicts_to_table(spark: SparkSession, d: Union[Dict, List[Dict]], tbl_name: str):
    if type(d) is dict:
        return _dict_to_table(d, spark, tbl_name)
    elif d and type(d) is list and type(d[0]) is dict:
        schema = _schema_from_fields(d[0])
        [rename_keys(e) for e in d]
        df = spark.createDataFrame(d, schema)
        df.createOrReplaceTempView(tbl_name)
        return df
    else:
        empty_df = spark.createDataFrame(spark.sparkContext.emptyRDD(), StructType([]))
        empty_df.createOrReplaceTempView(tbl_name)
        return empty_df


def _dict_to_table(d: dict, spark: SparkSession, tbl_name: str):
    schema = _schema_from_fields(d)
    rename_keys(d)
    if type(d) is list:
        data = d
    else:
        data = [d]
    df = spark.createDataFrame(data, schema)
    df.createOrReplaceTempView(tbl_name)
    return df


def _schema_from_fields(d: dict):
    fields = []
    for key in d.keys():
        assert ':' in key, 'expecting `name:type` in key {}'.format(key)
        name = key.split(":")[0]
        col_type = key.split(":")[1]
        if col_type == "str":
            fields.append(StructField(name, StringType()))
        elif col_type == "int":
            fields.append(StructField(name, IntegerType()))
        elif col_type == "float":
            fields.append(StructField(name, FloatType()))
        elif col_type == "bool":
            fields.append(StructField(name, BooleanType()))
        elif col_type == "date":
            fields.append(StructField(name, DateType()))
        elif col_type == "timestamp":
            fields.append(StructField(name, TimestampType()))
        elif col_type == "long":
            fields.append(StructField(name, LongType()))
        else:
            raise TypeError("Can't do anything with {} type".format(col_type))

    return StructType(fields)