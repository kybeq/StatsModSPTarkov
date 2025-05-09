const fs = require("fs");
const path = require("path");
const http = require("http"); // Zapewniamy, że to http

const FLASK_API_HOSTNAME = "127.0.0.1";
const FLASK_API_PORT = 5000;

class DetailedStatsTrackerFikaFinalPatch {
  constructor() {
    this.logger = null;
    this.jsonUtil = null;
    this.databaseServer = null;
    this.saveServer = null;
    this.profileHelper = null;
    this.ragfairPriceService = null;
    this.fikaInsuranceServiceInstance = null;
    this.locationLifecycleServiceInstance = null;
    this.persistentStats = {};
    this.modConfig = {};
    this.currentRaidInfo = null;
    this.setDefaultConfig();
    this.initializePersistentStats();
  }

  async sendToFlask(endpointPath, dataToSend) {
    const currentLogger = this.logger || {
      info: () => {},
      error: console.error,
    };
    try {
      const serializedData = JSON.stringify(dataToSend);
      const options = {
        hostname: FLASK_API_HOSTNAME,
        port: FLASK_API_PORT,
        path: endpointPath,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(serializedData),
        },
      };
      const req = http.request(options, (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          // res.on("data", (d) => process.stdout.write(d)); // Opcjonalne logowanie odpowiedzi błędu
          currentLogger.error(
            `[DST] Flask ERR ${options.path}: ${res.statusCode}`
          );
        }
      });
      req.on("error", (e) =>
        currentLogger.error(`[DST] HTTP ERR ${options.path}: ${e.message}`)
      );
      req.write(serializedData);
      req.end();
    } catch (e) {
      currentLogger.error(
        `[DST] SendToFlask EXC (${endpointPath}): ${e.message}`
      );
    }
  }

  async notifyFlaskConnected() {
    await this.sendToFlask(`/api/mod/connect`, {
      mod: "DetailedStatsTracker",
      status: "connected_final_minimal",
    });
  }

  postDBLoad(container) {
    try {
      this.jsonUtil = container.resolve("JsonUtil");
      this.databaseServer = container.resolve("DatabaseServer");
      this.saveServer = container.resolve("SaveServer");
      this.profileHelper = container.resolve("ProfileHelper");
      try {
        container.resolve("StaticRouterModService");
      } catch (e) {} // Ignoruj, jeśli nie ma
      if (
        !this.jsonUtil ||
        !this.databaseServer ||
        !this.saveServer ||
        !this.profileHelper
      ) {
        (this.logger || console).error(
          "[DST] Failed to resolve core SPT services."
        );
      }
      this.attemptFikaPatchStart(container);
      this.attemptFikaPatchEnd(container);
      this.loadConfig();
      this.loadPersistentStats();
      this.notifyFlaskConnected().catch((e) =>
        (this.logger || console).error(
          "[DST] NotifyFlask failed in postDBLoad:",
          e.message
        )
      );
      (this.logger || console).info("[DST] Mod initialized.");
    } catch (e) {
      (this.logger || console).error(
        `[DST] CRITICAL postDBLoad ERR: ${e}\n${e.stack}`
      );
    }
  }

  attemptFikaPatchStart(container) {
    try {
      const locationService = container.resolve("LocationLifecycleService");
      if (
        locationService &&
        typeof locationService.startLocalRaid === "function"
      ) {
        const originalStartLocalRaid = locationService.startLocalRaid;
        locationService.startLocalRaid = (sessionId, request) => {
          let originalResult = null;
          try {
            originalResult = originalStartLocalRaid.call(
              locationService,
              sessionId,
              request
            );
          } catch (e) {
            (this.logger || console).error(
              `[DST] ERR calling original startLocalRaid: ${e.stack}`
            );
            return originalResult;
          }
          try {
            let pmcData = null;
            if (this.profileHelper) {
              try {
                pmcData =
                  this.profileHelper.getPmcProfile(sessionId) ||
                  this.profileHelper.getFullProfile(sessionId);
              } catch (e) {}
            }
            if (sessionId && pmcData && this.jsonUtil) {
              try {
                this.currentRaidInfo = {
                  sessionId: sessionId,
                  profileAtStart: this.jsonUtil.clone(pmcData),
                  map: request?.location?.toLowerCase() || "unknown",
                  startTime: Date.now(),
                  timeOfDay:
                    request?.timeAndWeatherSettings?.timeVariant ||
                    originalResult?.locationLoot?.TimeAndWeatherSettings
                      ?.timeVariant ||
                    "unknown",
                  weather:
                    request?.timeAndWeatherSettings?.weatherSettings
                      ?.cloudiness !== undefined
                      ? request.timeAndWeatherSettings.weatherSettings
                          .cloudiness
                      : request?.timeAndWeatherSettings?.weatherSettings
                          ?.Cloudiness !== undefined
                      ? request.timeAndWeatherSettings.weatherSettings
                          .Cloudiness
                      : "unknown",
                };
              } catch (cloneError) {
                this.currentRaidInfo = null;
              }
            }
            if (pmcData) {
              this.sendToFlask(`/api/raid/start`, {
                sessionId: sessionId,
                request: {
                  location: request?.location,
                  timeAndWeatherSettings: request?.timeAndWeatherSettings,
                  playerProfile: { Info: pmcData.Info },
                },
              }).catch((e) =>
                (this.logger || console).error(
                  `[DST] ERR sending start data: ${e.message}`
                )
              );
            }
          } catch (e) {
            (this.logger || console).error(
              `[DST] ERR in custom start processing: ${e.stack}`
            );
          }
          return originalResult;
        };
      } else {
        (this.logger || console).error(
          "[DST] FAILED to patch LocationLifecycleService.startLocalRaid"
        );
      }
    } catch (e) {
      (this.logger || console).error(
        `[DST] CRITICAL ERR patching LocationLifecycleService: ${e.stack}`
      );
    }
  }

  attemptFikaPatchEnd(container) {
    let patchedRaidEnd = false;
    try {
      const fikaInsuranceService = container.resolve("FikaInsuranceService");
      if (
        fikaInsuranceService &&
        typeof fikaInsuranceService.onEndLocalRaidRequest === "function"
      ) {
        const originalOnEndLocalRaidRequest =
          fikaInsuranceService.onEndLocalRaidRequest;
        fikaInsuranceService.onEndLocalRaidRequest = (
          sessionId,
          matchId,
          request
        ) => {
          let originalResult;
          try {
            originalResult = originalOnEndLocalRaidRequest.call(
              fikaInsuranceService,
              sessionId,
              matchId,
              request
            );
          } catch (e) {
            (this.logger || console).error(
              `[DST] ERR calling original Fika onEndLocalRaidRequest: ${e.stack}`
            );
            return originalResult;
          }
          try {
            if (request && request.results && request.results.profile) {
              this.sendToFlask(`/api/raid/end`, {
                sessionId,
                matchId,
                request,
              }).catch((e) =>
                (this.logger || console).error(
                  `[DST] ERR sending end data (Fika): ${e.message}`
                )
              );
            }
            if (
              !this.currentRaidInfo ||
              this.currentRaidInfo.sessionId !== sessionId
            ) {
              /* Logika dla braku currentRaidInfo */
            } else {
              const exitStatus =
                request?.results?.result?.toLowerCase() ||
                request?.exit?.toLowerCase() ||
                "unknown";
              const exitName =
                request?.exitName || request?.results?.exitName || null;
              const offraidData = request?.results?.profile;
              if (
                offraidData &&
                typeof offraidData === "object" &&
                offraidData.Info &&
                offraidData.Stats &&
                offraidData.Stats.Eft
              ) {
                this.processRaidEndData(
                  sessionId,
                  exitStatus,
                  exitName,
                  offraidData
                );
              } else {
                if (
                  this.currentRaidInfo &&
                  this.currentRaidInfo.sessionId === sessionId
                )
                  this.currentRaidInfo = null;
              }
            }
          } catch (e) {
            if (
              this.currentRaidInfo &&
              this.currentRaidInfo.sessionId === sessionId
            )
              this.currentRaidInfo = null;
            (this.logger || console).error(
              `[DST] ERR in custom Fika end processing: ${e.stack}`
            );
          }
          return originalResult;
        };
        patchedRaidEnd = true;
      }
    } catch (e) {
      /* cicho, jeśli Fika nie istnieje */
    }

    if (!patchedRaidEnd) {
      try {
        const inraidController = container.resolve("InraidController");
        if (
          inraidController &&
          typeof inraidController.raidEnd === "function"
        ) {
          const originalRaidEnd = inraidController.raidEnd;
          inraidController.raidEnd = (sessionId, saveProfileRequest) => {
            let originalResult;
            try {
              originalResult = originalRaidEnd.call(
                inraidController,
                sessionId,
                saveProfileRequest
              );
            } catch (e) {
              (this.logger || console).error(
                `[DST] ERR calling original InraidController.raidEnd: ${e.stack}`
              );
              return originalResult;
            }
            try {
              const offraidData = saveProfileRequest.profile;
              const exitStatus = saveProfileRequest.eftData.exit.toLowerCase();
              const exitName = saveProfileRequest.eftData.exitName;
              if (
                offraidData &&
                typeof offraidData === "object" &&
                offraidData.Info &&
                offraidData.Stats &&
                offraidData.Stats.Eft
              ) {
                this.sendToFlask(`/api/raid/end`, {
                  sessionId: sessionId,
                  request: {
                    results: {
                      result: exitStatus,
                      exitName: exitName,
                      playTime: saveProfileRequest.eftData.gameTime,
                      profile: offraidData,
                    },
                  },
                }).catch((e) =>
                  (this.logger || console).error(
                    `[DST] ERR sending end data (SPT): ${e.message}`
                  )
                );
                if (
                  !this.currentRaidInfo ||
                  this.currentRaidInfo.sessionId !== sessionId
                ) {
                  /* Logika */
                } else {
                  this.processRaidEndData(
                    sessionId,
                    exitStatus,
                    exitName,
                    offraidData
                  );
                }
              } else {
                if (
                  this.currentRaidInfo &&
                  this.currentRaidInfo.sessionId === sessionId
                )
                  this.currentRaidInfo = null;
              }
            } catch (e) {
              if (
                this.currentRaidInfo &&
                this.currentRaidInfo.sessionId === sessionId
              )
                this.currentRaidInfo = null;
              (this.logger || console).error(
                `[DST] ERR in custom SPT end processing: ${e.stack}`
              );
            }
            return originalResult;
          };
        } else {
          (this.logger || console).error(
            "[DST] FAILED to patch InraidController.raidEnd"
          );
        }
      } catch (e) {
        (this.logger || console).error(
          `[DST] CRITICAL ERR patching InraidController: ${e.stack}`
        );
      }
    }
  }

  saveJsonToDebugFile(filename, data) {
    /* Minimalne lub puste, jeśli niepotrzebne */
  }
  logObjectDataForDebugging(label, data) {
    /* Minimalne lub puste */
  }

  processRaidEndData(sessionId, exitStatus, exitName, offraidData) {
    if (
      !this.currentRaidInfo ||
      this.currentRaidInfo.sessionId !== sessionId ||
      !this.databaseServer ||
      !this.jsonUtil
    ) {
      this.currentRaidInfo = null;
      return;
    }
    const raidInfo = this.currentRaidInfo;
    this.currentRaidInfo = null;
    const endTime = Date.now();
    const durationSeconds = Math.floor((endTime - raidInfo.startTime) / 1000);
    try {
      let expGainedInRaid = 0;
      if (
        raidInfo.profileAtStart?.Info?.Experience !== undefined &&
        offraidData.Info?.Experience !== undefined
      ) {
        expGainedInRaid =
          offraidData.Info.Experience - raidInfo.profileAtStart.Info.Experience;
      } else {
        expGainedInRaid = offraidData.Info?.Experience || 0;
      }
      const processedRaidStats = {
        map: raidInfo.map,
        startTime: raidInfo.startTime,
        endTime: endTime,
        durationSeconds: durationSeconds,
        timeOfDay: raidInfo.timeOfDay,
        weather: raidInfo.weather,
        status: exitStatus,
        exitName: exitName || "N/A",
        kills: [],
        loot: { itemsAdded: [], itemsRemoved: [], totalValueGained: 0 },
        expGained: expGainedInRaid,
        skillProgress: {},
      };
      if (offraidData.Stats?.Eft?.Victims) {
        const dbItems = this.databaseServer.getTables().templates.items;
        for (const victim of offraidData.Stats.Eft.Victims) {
          let weaponName = "Unknown";
          const weaponIdClean = victim.Weapon?.split(" ")[0];
          if (weaponIdClean && dbItems[weaponIdClean]?._name)
            weaponName = dbItems[weaponIdClean]._name;
          else if (victim.Weapon) weaponName = victim.Weapon;
          processedRaidStats.kills.push({
            name: victim.Name || "?",
            role: victim.Role || "?",
            level: victim.Level || 0,
            weapon: weaponName,
            distance: victim.Distance || 0,
            bodyPart: victim.BodyPart || "?",
            time: victim.Time || 0,
          });
        }
      }
      this.updatePersistentStats(processedRaidStats);
      this.savePersistentStats();
    } catch (e) {
      (this.logger || console).error(
        `[DST] ERR in processRaidEndData: ${e.stack}`
      );
    }
  }

  onRaidStart(url, info, sessionId, pmcData) {
    /* Ignored */
  }
  onRaidEnd(url, info, sessionId, exitStatus, exitName, offraidData) {
    /* Ignored */
  }

  loadConfig() {
    if (!this.jsonUtil) {
      this.setDefaultConfig();
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    try {
      const configDir = path.dirname(configPath);
      if (!fs.existsSync(configDir))
        fs.mkdirSync(configDir, { recursive: true });
      if (fs.existsSync(configPath)) {
        this.modConfig = this.jsonUtil.deserialize(
          fs.readFileSync(configPath, "utf8")
        );
        this.ensureDefaultConfigValues();
      } else {
        this.setDefaultConfig();
        this.saveConfig();
      }
    } catch (e) {
      this.setDefaultConfig();
    }
  }

  setDefaultConfig() {
    if (typeof this.modConfig !== "object" || this.modConfig === null)
      this.modConfig = {};
    this.modConfig = {
      ...{
        enabled: true,
        trackKills: true,
        trackLootValue: false,
        maxRaidHistory: 50,
        persistentStatsFilePath: "stats_data.json",
      },
      ...this.modConfig,
    };
    return this.modConfig;
  }

  ensureDefaultConfigValues() {
    const defaultConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    if (typeof this.modConfig !== "object" || this.modConfig === null)
      this.modConfig = {};
    for (const key in defaultConfig) {
      if (this.modConfig[key] === undefined)
        this.modConfig[key] = defaultConfig[key];
    }
  }

  saveConfig() {
    if (!this.jsonUtil) return;
    const configPath = path.join(__dirname, "config", "config.json");
    const configDir = path.dirname(configPath);
    try {
      if (!fs.existsSync(configDir))
        fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(
        configPath,
        this.jsonUtil.serialize(this.modConfig, true),
        "utf8"
      );
    } catch (e) {
      (this.logger || console).error(`[DST] ERR saving config: ${e}`);
    }
  }

  loadPersistentStats() {
    if (!this.jsonUtil) {
      this.initializePersistentStats();
      return;
    }
    const filePath = path.join(
      __dirname,
      this.modConfig.persistentStatsFilePath || "stats_data.json"
    );
    try {
      const dirPath = path.dirname(filePath);
      if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
      if (fs.existsSync(filePath)) {
        const fileContent = fs.readFileSync(filePath, "utf8");
        if (fileContent.trim() === "") {
          this.initializePersistentStats();
        } else {
          this.persistentStats = this.jsonUtil.deserialize(fileContent);
          if (
            typeof this.persistentStats !== "object" ||
            this.persistentStats === null ||
            Object.keys(this.persistentStats).length === 0
          ) {
            this.initializePersistentStats();
          }
        }
      } else {
        this.initializePersistentStats();
      }
    } catch (e) {
      this.initializePersistentStats();
    }
  }

  initializePersistentStats() {
    this.persistentStats = {
      totalRaids: 0,
      totalSurvived: 0,
      totalKills: { pmc: 0, scav: 0, boss: 0, other: 0 },
      totalExp: 0,
      averageSurvivalRate: 0,
      raidHistory: [],
      playerStatsSnapshot: {},
    };
  }

  savePersistentStats() {
    if (!this.jsonUtil) return;
    const filePath = path.join(
      __dirname,
      this.modConfig.persistentStatsFilePath || "stats_data.json"
    );
    try {
      const modDir = path.dirname(filePath);
      if (!fs.existsSync(modDir)) fs.mkdirSync(modDir, { recursive: true });
      fs.writeFileSync(
        filePath,
        this.jsonUtil.serialize(this.persistentStats, true),
        "utf8"
      );
    } catch (e) {
      (this.logger || console).error(`[DST] ERR saving persistent stats: ${e}`);
    }
  }

  updatePersistentStats(processedRaidStats) {
    if (!this.persistentStats || typeof this.persistentStats !== "object")
      this.initializePersistentStats();
    if (
      !this.persistentStats.totalKills ||
      typeof this.persistentStats.totalKills !== "object"
    )
      this.persistentStats.totalKills = { pmc: 0, scav: 0, boss: 0, other: 0 };
    if (!Array.isArray(this.persistentStats.raidHistory))
      this.persistentStats.raidHistory = [];
    this.persistentStats.totalRaids =
      (this.persistentStats.totalRaids || 0) + 1;
    this.persistentStats.totalSurvived =
      this.persistentStats.totalSurvived || 0;
    Object.keys(this.persistentStats.totalKills).forEach(
      (k) =>
        (this.persistentStats.totalKills[k] =
          this.persistentStats.totalKills[k] || 0)
    );
    this.persistentStats.totalExp =
      (this.persistentStats.totalExp || 0) +
      (processedRaidStats.expGained || 0);
    if (processedRaidStats.status === "survived")
      this.persistentStats.totalSurvived++;
    if (processedRaidStats.kills?.length) {
      for (const kill of processedRaidStats.kills) {
        const role = kill.role?.toLowerCase() || "other";
        if (role.includes("bear") || role.includes("usec"))
          this.persistentStats.totalKills.pmc++;
        else if (role.includes("savage") || role.includes("playerscav"))
          this.persistentStats.totalKills.scav++;
        else if (role.includes("boss")) this.persistentStats.totalKills.boss++;
        else this.persistentStats.totalKills.other++;
      }
    }
    this.persistentStats.averageSurvivalRate =
      this.persistentStats.totalRaids > 0
        ? parseFloat(
            (
              (this.persistentStats.totalSurvived /
                this.persistentStats.totalRaids) *
              100
            ).toFixed(2)
          )
        : 0;
    this.persistentStats.raidHistory.push(processedRaidStats);
    const maxHistory = this.modConfig.maxRaidHistory || 50;
    if (this.persistentStats.raidHistory.length > maxHistory)
      this.persistentStats.raidHistory.shift();
  }
}

module.exports = { mod: new DetailedStatsTrackerFikaFinalPatch() };
