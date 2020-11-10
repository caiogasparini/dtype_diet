"""Propose RAM-saving changes in a DataFrame"""

import pandas as pd
import numpy as np
from collections import namedtuple


# TODO
# more tests
#   test float64->float32->float16
# consider uint64/32/16/8
# does the "object" check work if col has non-str items?
# enable approx-equal with np.close (note for big nbrs, a big delta is "acceptable" with this)

# convert_dtypes converts e.g. int64 to Int64 (nullable) regardless of nulls, also obj->string
# so it doesn't save RAM but it does suggest new safer datatypes
# https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.convert_dtypes.html

# For a dtype count the nbr of conversions that aren't equal, the RAM cost
# of the conversion and the column name
AsType = namedtuple('AsType', ['dtype', 'nbr_different', 'nbytes', 'col'])


def count_errors(ser, new_dtype, unsafe=False):
    """After converting ser to new dtype, count whether items have isclose()"""
    errors = 'ignore' if unsafe else None
    tmp_ser = ser.astype(new_dtype, errors=errors)
    # metric will be a list of Trues if the change has equivalent value, False otherwise
    # checks for approx equal which may not be what we want
    #metric = np.isclose(ser, tmp_ser)
    metric = ser == tmp_ser
    nbytes = tmp_ser.memory_usage(deep=True) 
    as_type = AsType(new_dtype, (~metric).sum(), nbytes, ser.name)
    return as_type


def map_dtypes_to_choices(ser):
    new_dtypes = {'int64': ['Int32', 'Int16', 'Int8'],
                  'float64': ['float32', 'float16'],
                  'object': ['category']}
    return new_dtypes.get(ser.dtype.name)


def get_smallest_valid_conversion(ser, unsafe):
    new_dtypes = map_dtypes_to_choices(ser)
    if new_dtypes:
        for new_dtype in reversed(new_dtypes):
            as_type = count_errors(ser, new_dtype, unsafe)
            if as_type.nbr_different == 0:
                return as_type
    return None


def get_improvement(as_type, current_nbytes):
    ram_usage_improvement = current_nbytes - as_type.nbytes
    report = (as_type.col, current_nbytes, None, None, None)
    if ram_usage_improvement > 0:
        report = (as_type.col, current_nbytes, as_type.nbytes, as_type.dtype, ram_usage_improvement)
    return report


def report_on_dataframe(df, unit="MB", unsafe=False):
    """[Report on columns that might be converted]

    Args:
        df ([type]): [description]
        unit (str, optional): [byte, MB, GB]. Defaults to "MB".
    """

    unit_map = {"MB": 1024, "GB": 1024*1024, "byte": 1}
    divide_by = unit_map[unit]
    list_of_conversions = []

    for col in df.columns:
        current_dtype = df[col].dtype
        as_type = get_smallest_valid_conversion(df[col], unsafe)
        nbytes = df[col].memory_usage(deep=True)
        msg = None
        if as_type:
            col, current_bytes, after_bytes, proposed_dtype, ram_usage_improvement = get_improvement(as_type, nbytes)
            current_memory = current_bytes / divide_by
            after_memory = after_bytes / divide_by if after_bytes else None
            ram_usage_improvement = ram_usage_improvement / divide_by if after_bytes else None

        list_of_conversions.append((col, current_dtype, proposed_dtype, current_memory, after_memory, ram_usage_improvement))
    columns = ['Column', 'Current dtype','Proposed dtype', f'Current Memory ({unit})', f'Proposed Memory ({unit})', f'Ram Usage Improvement ({unit})']
    report_df = pd.DataFrame(list_of_conversions, columns=columns)
    report_df['Ram Usage Improvement (%)'] =  report_df[f'Ram Usage Improvement ({unit})'] / report_df[f'Current Memory ({unit})']
    report_df = report_df.set_index('Column')
    return report_df

def optimize_dtypes(df, proposed_df, unsafe=False):
    new_df = df.copy()
    errors = 'ignore' if unsafe else None
    for col in df.columns:
        new_dtype = proposed_df.loc[col, 'Proposed dtype']
        new_df[col] = new_df[col].astype(new_dtype, errors=errors)
    return new_df
def test_ser_ints():
    # check for low simple int
    ser = pd.Series([1] * 3)
    as_type = count_errors(ser, 'int32')
    assert as_type.nbr_different == 0
    as_type = count_errors(ser, 'int16')
    assert as_type.nbr_different == 0
    as_type = count_errors(ser, 'int8')
    assert as_type.nbr_different == 0

    # check for int needing bigger than int16
    ser = pd.Series([65536] * 3)
    as_type = count_errors(ser, 'int32')
    assert as_type.nbr_different == 0
    as_type = count_errors(ser, 'int16')
    assert as_type.nbr_different == 3
    as_type = count_errors(ser, 'int8')
    assert as_type.nbr_different == 3


if __name__ == "__main__":
    print("Given a dataframe, check for lowest possible conversions:")

    nbr_rows = 100
    df = pd.DataFrame()
    df['a'] = [0] * nbr_rows
    df['b'] = [256] * nbr_rows
    df['c'] = [65_536] * nbr_rows
    df['d'] = [1_100.0] * nbr_rows
    df['e'] = [100_101.0] * nbr_rows
    df['str_a'] = ['hello'] * nbr_rows
    df['str_b'] = [str(n) for n in range(nbr_rows)]
    report_on_dataframe(df)

    print("convert_dtypes does a slightly different job:")
    print(df.convert_dtypes())
