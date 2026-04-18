import numpy as np

top = []
for r, s, t in [
    #(10, 90, 0),
    #(20, 80, 0),
    #(30, 70, 0),
    #(40, 60, 0)
    (i, j, 0) for i in range(0, 101, 1) for j in range(0, 101, 1) if i + j <= 100

]: 
    research = 200000 * np.log(1+r) / np.log(1+100)
    scale =  7 * (s / 100)
    speed = 0.1 + 0.8 * (t / 100)
    budget_used = 50000 * (r/100 + s/100 + t/100)
    pnl = (research * scale * speed) - budget_used
    # print(f"r={r}, s={s}, t={t} => research={research:.2f}, scale={scale:.2f}, speed={speed:.2f}, budget_used={budget_used:.2f}, pnl={pnl:.2f}")
    top.append((r, s, t, pnl))
top.sort(key=lambda x: x[3], reverse=True)
print("\nTop 10 combinations:", top[:10])

optimal = top[0]
r, s, t, benchmark_pnl = optimal
steps = [(r, s, t, 0.1, 0)]
speed_r_s_optimal = {0: (r, s), 100: (0, 0)}

while r > 0 and s > 0:
    print(r, s)
    
    if r > 0:
        r -= 1
        research = 200000 * np.log(1+r) / np.log(1+100)
        scale =  7 * (s / 100)
        
        budget_used = 50000 * (r/100 + s/100 + t/100)
        speed_threshold = (benchmark_pnl + budget_used) / (research * scale) # this is the speed needed to break even with benchmark pnl
        if speed_threshold < 0.1 or speed_threshold > 0.9:
            speed_threshold_percent = -1
        else:
            speed_threshold_percent = (speed_threshold - 0.1) / 0.8 * 100 # convert back to percentage of t
        d = {}
        if speed_threshold_percent != -1:
            for i in range(1, 5):
                speed = speed_threshold + (0.9-speed_threshold) * (i / 5)
                speed_threshold_percent_temp = (speed - 0.1) / 0.8 * 100
                pnl2 = (research * scale * speed) - budget_used
                d[f'{round(speed_threshold_percent_temp, 2)}%'] = round(pnl2, 2)

        
        pnl1_no_speed = (research * scale) - budget_used

        r += 1
    else:
        pnl1_no_speed = 0
    
    if s > 0:
        s -= 1
        research = 200000 * np.log(1+r) / np.log(1+100)
        scale =  7 * (s / 100)
        budget_used = 50000 * (r/100 + s/100 + t/100)
        
        speed_threshold = (benchmark_pnl + budget_used) / (research * scale) # this is the speed needed to break even with benchmark pnl
        if speed_threshold < 0.1 or speed_threshold > 0.9:
            speed_threshold_percent = -1
        else:
            speed_threshold_percent = (speed_threshold - 0.1) / 0.8 * 100 # convert back to percentage of t

        d = {}
        if speed_threshold_percent != -1:
            for i in range(0, 6):
                speed = speed_threshold + (0.9-speed_threshold) * (i / 5)
                speed_threshold_percent_temp = (speed - 0.1) / 0.8 * 100
                pnl2 = (research * scale * speed) - budget_used
                d[f'{round(speed_threshold_percent_temp, 2)}%'] = round(pnl2, 2)

        pnl2_no_speed = (research * scale) - budget_used
        s += 1
    else:
        pnl2_no_speed = 0

    print(pnl1_no_speed, pnl2_no_speed)
    if pnl1_no_speed > pnl2_no_speed and r > 0:
        r -= 1
    else:
        s -= 1
    t += 1

    steps.append((r, s, t, f">= {round(speed_threshold_percent, 2)}% speed", d))
    speed_r_s_optimal[t] = (r, s)

print(steps)
for r, s, t, threshold, d in steps:
    print(f"r={r}, s={s}, t={t}, speed_thresholds={d}")


# Simulate the curve
# Pretend this is the distribution, find the best speed for it
cdf = [0 for i in range(101)]
cdf[0] = 10
cdf[20:30] = [3] * 10
cdf[30:40] = [6] * 10
cdf[40:50] = [8] * 10
cdf[50:60] = [6] * 10
cdf[60:70] = [4] * 10
cdf[70:76] = [1] * 6 # At very high speed it doesnt make sense anymore

sm = sum(cdf)
# Normalize cdf
cdf = [x / sm for x in cdf]

best_speed = -1
best_pnl = 0

for speed in range(101):
    r, s = speed_r_s_optimal[speed]
    t = speed
    research = 200000 * np.log(1+r) / np.log(1+100)
    scale =  7 * (s / 100)
    speed = 0.1 + 0.8 * sum(cdf[:t+1])
    print('test', speed, sum(cdf[:t+1]))
    budget_used = 50000 * (r/100 + s/100 + t/100)
    pnl = (research * scale * speed) - budget_used
    if pnl > best_pnl:
        best_pnl = pnl
        best_speed = speed

print(f"Best speed: {best_speed}, Best pnl: {best_pnl} for this simulated distribution")