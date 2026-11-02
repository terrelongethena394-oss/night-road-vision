from pathlib import Path

path=Path('E:/FPGA_Enhance_Work/road_local_enhance_20261029_r2/reference/retinex_reference.txt')
lines=path.read_text(encoding='utf-8').splitlines()
for start,end in [(1,28),(110,183),(262,286),(314,364)]:
    print('\nLINES',start,end)
    for n in range(start-1,min(end,len(lines))):
        print(f'{n+1}: '+lines[n].encode('ascii','backslashreplace').decode())
