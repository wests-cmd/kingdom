"""Bounded work on battery; unknown power is never treated as charging."""
import math


def validate_power(value):
    if not isinstance(value,dict) or set(value)!={'status','battery_percent','plugged'}:
        raise ValueError('Invalid power measurement')
    status=value['status'];percent=value['battery_percent'];plugged=value['plugged']
    if status=='battery':
        if type(percent) not in (int,float) or not math.isfinite(percent) or not 0<=percent<=100 or type(plugged) is not bool:
            raise ValueError('Invalid battery measurement')
    elif status not in {'unknown','no_battery'} or percent is not None or plugged is not None:
        raise ValueError('Invalid power state')
    return dict(value)


def power_budget(power,estimated_seconds=10):
    try:sample=validate_power(power)
    except ValueError:sample={'status':'unknown','battery_percent':None,'plugged':None}
    if type(estimated_seconds) not in (int,float) or not math.isfinite(estimated_seconds) or estimated_seconds<=0:
        raise ValueError('Supply a positive bounded work estimate')
    if sample['status']=='no_battery' or sample['plugged'] is True:
        limit=600;reason='External power or no battery reported; normal bounded work'
    elif sample['status']=='unknown':
        limit=15;reason='Power unknown; only short checkpointed work'
    elif sample['battery_percent']<=20:
        limit=0;reason='Battery reserve at or below 20%; wait for charging'
    elif sample['battery_percent']<40:
        limit=15;reason='On battery below 40%; only short checkpointed work'
    else:
        limit=60;reason='On battery; cap work at one minute and checkpoint'
    return {'allowed':estimated_seconds<=limit,'max_seconds':limit,'reason':reason,
            'power_status':sample['status'],'battery_percent':sample['battery_percent'],'plugged':sample['plugged']}
