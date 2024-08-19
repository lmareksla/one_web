import pandas as pd
import matplotlib.pyplot as plt
import copy
import numpy as np

if __name__ == '__main__':
    
    file_in_path_name = "/home/lukas/file/analysis/one_web/map_power_cycling_detector/Mapping_results_2023-12-01_2024-01-31.csv"


    data = pd.read_csv(file_in_path_name)


    fig_eart_path_name = "./fig/Equirectangular-projection.jpg"

    fig, axs = plt.subplots(2,1,figsize=(9,9))

    # image_eart = mpimg.imread(fig_eart_path_name)
    image_eart = plt.imread(fig_eart_path_name)
    
    axs[0].imshow(image_eart, extent=[-180,180,-90,90], alpha=0.5)
    axs[1].imshow(image_eart, extent=[-180,180,-90,90], alpha=0.5)

    data_long = copy.deepcopy(data["longitude"])
    data_long = np.array(data_long)

    print(data_long)

    data_long[data_long > 180] += 1000
    data_long[data_long < 180] += 180
    data_long[data_long > 1180] -= 1180

    axs[0].scatter(data_long-180, data["latitude"], color="C3")
    axs[0].set_title(f"position of power cycling of detector, sum {len(data)}")
    axs[0].set_xlabel("longitude [deg]")
    axs[0].set_ylabel("latitude [deg]")

    hist2d_res = axs[1].hist2d(data_long-180, data["latitude"], bins=[20,10], alpha=0.5)
    axs[1].set_title(f"position of power cycling of detector, sum {len(data)}")
    axs[1].set_xlabel("longitude [deg]")
    axs[1].set_ylabel("latitude [deg]")
    cbar = fig.colorbar(hist2d_res[3], ax=axs[1], alpha=1, fraction=0.03, pad=0.04)

    plt.tight_layout()        

    plt.show()