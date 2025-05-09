const fs = require("fs").promises;
const path = require("path");
const https = require("http");

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

    this.apiUrl = "http://127.0.0.1:5000/api";
    this.initialize();
  }

  async initialize() {
    await this.ensureDebugLogFolderExists();
    this.setDefaultConfig();
    this.initializePersistentStats();
    await this.notifyFlaskConnected();
  }

  async notifyFlaskConnected() {
    const data = { mod: "DetailedStatsTracker", status: "connected" };
    const serializedData = JSON.stringify(data);
    const options = {
      hostname: "127.0.0.1",
      port: 5000,
      path: "/api/mod/connect",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(serializedData),
      },
    };

    try {
      await new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            this.logger?.info("Notified Flask: Mod connected");
            resolve();
          } else {
            reject(new Error(`Flask API error: ${res.statusCode}`));
          }
        });

        req.on("error", (e) => {
          reject(new Error(`HTTP request failed: ${e.message}`));
        });

        req.write(serializedData);
        req.end();
      });
    } catch (e) {
      this.logger?.error(`Failed to notify Flask: ${e.message}`);
    }
  }

  async ensureDebugLogFolderExists() {
    const debugFolderPath = path.join(__dirname, "debug_logs");
    try {
      await fs.mkdir(debugFolderPath, { recursive: true });
      this.logger?.info(`Created debug log folder: ${debugFolderPath}`);
    } catch (e) {
      this.logger?.error(`Could not create debug log folder: ${e}`);
    }
  }

  preSptLoad(container) {
    try {
      this.logger = container.resolve("WinstonLogger");
      this.logger?.info("Logger resolved successfully.");
    } catch (e) {
      console.error(`Error resolving WinstonLogger: ${e}`);
    }
    this.ensureDebugLogFolderExists();
  }

  postDBLoad(container) {
    if (!this.logger) {
      console.warn("Logger not initialized in preSptLoad.");
    }
    try {
      this.initializeServices(container);
      this.patchServices(container);
      this.loadConfig();
      this.loadPersistentStats();
      this.logger?.info("Mod finished postDBLoad initialization.");
    } catch (e) {
      this.logger?.error(`CRITICAL ERROR during postDBLoad: ${e}\n${e.stack}`);
    }
  }

  initializeServices(container) {
    this.jsonUtil = container.resolve("JsonUtil");
    this.databaseServer = container.resolve("DatabaseServer");
    this.saveServer = container.resolve("SaveServer");
    this.profileHelper = container.resolve("ProfileHelper");
    this.ragfairPriceService = container.resolve("RagfairPriceService");

    if (
      !this.jsonUtil ||
      !this.databaseServer ||
      !this.saveServer ||
      !this.profileHelper
    ) {
      this.logger?.error("Failed to resolve core SPT services.");
    } else {
      this.logger?.info("Core SPT services resolved successfully.");
    }
  }

  patchServices(container) {
    this.attemptFikaPatchStart(container);
    this.attemptFikaPatchEnd(container);
  }

  attemptFikaPatchStart(container) {
    try {
      const locationService = container.resolve("LocationLifecycleService");
      if (
        locationService &&
        typeof locationService.startLocalRaid === "function"
      ) {
        this.locationLifecycleServiceInstance = locationService;
        const originalStartLocalRaid = locationService.startLocalRaid;
        locationService.startLocalRaid = this.patchMethod(
          originalStartLocalRaid,
          locationService,
          this.handleRaidStart.bind(this),
          "startLocalRaid"
        );
        this.logger?.info(
          "LocationLifecycleService.startLocalRaid patched successfully."
        );
      } else {
        this.logger?.error(
          "FAILED to resolve LocationLifecycleService or its method."
        );
      }
    } catch (e) {
      this.logger?.error(
        `CRITICAL Error patching LocationLifecycleService: ${e}\n${e.stack}`
      );
    }
  }

  attemptFikaPatchEnd(container) {
    try {
      const fikaInsuranceService = container.resolve("FikaInsuranceService");
      if (
        fikaInsuranceService &&
        typeof fikaInsuranceService.onEndLocalRaidRequest === "function"
      ) {
        this.fikaInsuranceServiceInstance = fikaInsuranceService;
        const originalOnEndLocalRaidRequest =
          fikaInsuranceService.onEndLocalRaidRequest;
        fikaInsuranceService.onEndLocalRaidRequest = this.patchMethod(
          originalOnEndLocalRaidRequest,
          fikaInsuranceService,
          this.handleRaidEnd.bind(this),
          "onEndLocalRaidRequest"
        );
        this.logger?.info(
          "FikaInsuranceService.onEndLocalRaidRequest patched successfully."
        );
      } else {
        this.logger?.error(
          "FAILED to resolve FikaInsuranceService or its method."
        );
      }
    } catch (e) {
      this.logger?.error(
        `CRITICAL Error patching FikaInsuranceService: ${e}\n${e.stack}`
      );
    }
  }

  patchMethod(originalMethod, context, handler, methodName) {
    return (...args) => {
      this.logger?.info(`${methodName} patched for session: ${args[0]}`);
      let result;
      try {
        result = originalMethod.apply(context, args);
        this.logger?.info(
          `Original ${methodName} finished for session: ${args[0]}`
        );
      } catch (e) {
        this.logger?.error(
          `Error calling original ${methodName}: ${e}\n${e.stack}`
        );
        return result;
      }
      handler(args, result);
      return result;
    };
  }

  async handleRaidStart([sessionId, request], result) {
    if (this.currentRaidInfo?.sessionId === sessionId) {
      this.logger?.warn(
        `Raid start already processed for session: ${sessionId}. Skipping.`
      );
      return;
    }

    try {
      const pmcData =
        this.profileHelper?.getPmcProfile(sessionId) ||
        this.profileHelper?.getFullProfile(sessionId);
      if (!pmcData) {
        this.logger?.error(`Failed to fetch pmcData for session: ${sessionId}`);
        return;
      }

      const mapName = request?.location?.toLowerCase() || "unknown";
      const timeOfDay =
        request?.timeAndWeatherSettings?.timeVariant ||
        result?.locationLoot?.TimeAndWeatherSettings?.timeVariant ||
        "unknown";

      this.currentRaidInfo = {
        sessionId,
        profileAtStart: this.jsonUtil?.clone(pmcData),
        map: mapName,
        startTime: Date.now(),
        timeOfDay,
      };

      await this.sendToFlask(`${this.apiUrl}/raid/start`, {
        sessionId,
        request,
        result,
      });
      this.logger?.info(`Raid started. Session: ${sessionId}, Map: ${mapName}`);
    } catch (e) {
      this.logger?.error(
        `Error during raid start processing: ${e}\n${e.stack}`
      );
    }
  }

  async handleRaidEnd([sessionId, matchId, request]) {
    try {
      if (
        !this.currentRaidInfo ||
        this.currentRaidInfo.sessionId !== sessionId
      ) {
        this.logger?.warn(
          `No matching raid start data for session: ${sessionId}`
        );
        return;
      }

      const exitStatus =
        request?.results?.result?.toLowerCase() ||
        request?.exit?.toLowerCase() ||
        "unknown";
      const exitName = request?.exitName || request?.results?.exitName || null;
      const offraidData = request?.results?.profile;

      if (this.isValidOffraidData(offraidData)) {
        this.logger?.info(
          `Raid ended. Session: ${sessionId}, Status: ${exitStatus}`
        );
        await this.sendToFlask(`${this.apiUrl}/raid/end`, {
          sessionId,
          matchId,
          request,
        });
        await this.processRaidEndData(
          sessionId,
          exitStatus,
          exitName,
          offraidData
        );
      } else {
        this.logger?.error(`Invalid offraidData for session: ${sessionId}`);
        this.currentRaidInfo = null;
      }
    } catch (e) {
      this.logger?.error(`Error during raid end processing: ${e}\n${e.stack}`);
      this.currentRaidInfo = null;
    }
  }

  async sendToFlask(endpoint, data) {
    if (!this.jsonUtil) {
      this.logger?.error("Cannot send data to Flask - jsonUtil missing.");
      return;
    }
    try {
      const serializedData = this.jsonUtil.serialize(data, true);
      const options = {
        hostname: "127.0.0.1",
        port: 5000,
        path: endpoint.replace("http://127.0.0.1:5000", ""),
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(serializedData),
        },
      };

      await new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
          let responseData = "";
          res.on("data", (chunk) => (responseData += chunk));
          res.on("end", () => {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              this.logger?.info(`Data sent to Flask: ${endpoint}`);
              resolve();
            } else {
              reject(new Error(`Flask API error: ${res.statusCode}`));
            }
          });
        });

        req.on("error", (e) => {
          reject(new Error(`HTTP request failed: ${e.message}`));
        });

        req.write(serializedData);
        req.end();
      });
    } catch (e) {
      this.logger?.error(`Failed to send data to Flask: ${e.message}`);
      this.logger?.debug(`Error details: ${e.stack}`);
    }
  }

  isValidOffraidData(data) {
    return (
      data &&
      typeof data === "object" &&
      data.Info &&
      data.Inventory &&
      data.Stats
    );
  }

  async processRaidEndData(sessionId, exitStatus, exitName, offraidData) {
    if (
      !this.currentRaidInfo ||
      this.currentRaidInfo.sessionId !== sessionId ||
      !this.databaseServer ||
      !this.jsonUtil
    ) {
      this.logger?.error("Invalid session or missing services!");
      this.currentRaidInfo = null;
      return;
    }

    const raidInfo = this.currentRaidInfo;
    this.currentRaidInfo = null;
    const endTime = Date.now();
    const durationSeconds = Math.floor((endTime - raidInfo.startTime) / 1000);
    this.logger?.info(
      `Processing raid end. Session: ${sessionId}, Status: ${exitStatus}, Duration: ${durationSeconds}s`
    );

    try {
      const processedRaidStats = {
        map: raidInfo.map,
        startTime: raidInfo.startTime,
        endTime,
        durationSeconds,
        timeOfDay: raidInfo.timeOfDay,
        weather: raidInfo.weather,
        status: exitStatus,
        exitName: exitName || "N/A",
        kills: [],
        loot: { itemsAdded: [], itemsRemoved: [], totalValueGained: 0 },
        expGained: offraidData.experience || 0,
        skillProgress: {},
        damageDealt: 0,
        shotsFired: 0,
        shotsHit: 0,
        headshots: 0,
      };

      if (offraidData.Stats?.OverallCounters?.Counters) {
        const counters = offraidData.Stats.OverallCounters.Counters;
        const findCounter = (key) =>
          counters.find((c) => c.Key === key)?.Value || 0;
        processedRaidStats.shotsFired = findCounter("Shots");
        processedRaidStats.shotsHit = findCounter("Hits");
        processedRaidStats.headshots = findCounter("Headshots");
      }

      if (offraidData.Stats?.Victims) {
        const dbItems = this.databaseServer.getTables().templates.items;
        for (const victim of offraidData.Stats.Victims) {
          let weaponName =
            victim.Weapon && dbItems[victim.Weapon]?._name
              ? dbItems[victim.Weapon]._name
              : victim.Weapon || "Unknown";
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
        this.logger?.info(
          `Processed ${processedRaidStats.kills.length} kills for session: ${sessionId}`
        );
      }

      await this.updatePersistentStats(processedRaidStats);
      await this.savePersistentStats();
    } catch (e) {
      this.logger?.error(`Error processing raid end data: ${e}\n${e.stack}`);
    }
  }

  async loadConfig() {
    if (!this.jsonUtil) {
      this.logger?.error("Cannot load config: JsonUtil not initialized!");
      this.setDefaultConfig();
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    try {
      const configContent = await fs.readFile(configPath, "utf8");
      this.modConfig = this.jsonUtil.deserialize(configContent);
      this.ensureDefaultConfigValues();
      this.logger?.info("Configuration loaded successfully.");
    } catch (e) {
      this.logger?.warn(`Error loading config: ${e}. Using default config.`);
      this.setDefaultConfig();
      await this.saveConfig();
    }
  }

  setDefaultConfig() {
    this.modConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    this.logger?.info("Default configuration set.");
  }

  ensureDefaultConfigValues() {
    const defaultConfig = this.setDefaultConfig();
    let changed = false;
    for (const key in defaultConfig) {
      if (this.modConfig[key] === undefined) {
        this.modConfig[key] = defaultConfig[key];
        changed = true;
      }
    }
    if (changed) {
      this.logger?.info("Added missing default config values.");
    }
  }

  async saveConfig() {
    if (!this.jsonUtil) {
      this.logger?.error("Cannot save config: JsonUtil not initialized!");
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    const configDir = path.join(__dirname, "config");
    try {
      await fs.mkdir(configDir, { recursive: true });
      await fs.writeFile(
        configPath,
        this.jsonUtil.serialize(this.modConfig, true),
        "utf8"
      );
      this.logger?.info(`Saved config file to: ${configPath}`);
    } catch (e) {
      this.logger?.error(`Could not save config file: ${e}`);
    }
  }

  async loadPersistentStats() {
    if (!this.jsonUtil) {
      this.logger?.error(
        "Cannot load persistent stats: JsonUtil not initialized!"
      );
      this.initializePersistentStats();
      return;
    }
    const filePath = path.join(
      __dirname,
      this.modConfig.persistentStatsFilePath || "stats_data.json"
    );
    try {
      const fileContent = await fs.readFile(filePath, "utf8");
      this.persistentStats = this.jsonUtil.deserialize(fileContent);
      if (
        !this.persistentStats ||
        typeof this.persistentStats !== "object" ||
        Object.keys(this.persistentStats).length === 0
      ) {
        this.logger?.warn(
          "Loaded stats empty or corrupted. Initializing empty stats."
        );
        this.initializePersistentStats();
      } else {
        this.logger?.info("Persistent stats loaded successfully.");
      }
    } catch (e) {
      this.logger?.warn(`Error loading stats: ${e}. Initializing empty stats.`);
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
    this.logger?.info("Initialized empty persistent stats.");
  }

  async savePersistentStats() {
    if (!this.jsonUtil) {
      this.logger?.error(
        "Cannot save persistent stats: JsonUtil not initialized!"
      );
      return;
    }
    const filePath = path.join(
      __dirname,
      this.modConfig.persistentStatsFilePath || "stats_data.json"
    );
    try {
      await fs.writeFile(
        filePath,
        this.jsonUtil.serialize(this.persistentStats, true),
        "utf8"
      );
      this.logger?.info("Persistent stats saved successfully.");
    } catch (e) {
      this.logger?.error(`Could not save persistent stats: ${e}`);
    }
  }

  async updatePersistentStats(processedRaidStats) {
    this.logger?.info(
      `Updating persistent stats for raid on ${processedRaidStats.map}.`
    );
    if (!this.persistentStats || typeof this.persistentStats !== "object") {
      this.initializePersistentStats();
    }

    this.persistentStats.totalRaids += 1;
    if (processedRaidStats.status === "survived") {
      this.persistentStats.totalSurvived += 1;
    }
    if (processedRaidStats.kills?.length) {
      for (const kill of processedRaidStats.kills) {
        const role = kill.role?.toLowerCase() || "other";
        if (role.includes("bear") || role.includes("usec")) {
          this.persistentStats.totalKills.pmc += 1;
        } else if (role.includes("savage") || role.includes("playerscav")) {
          this.persistentStats.totalKills.scav += 1;
        } else if (role.includes("boss")) {
          this.persistentStats.totalKills.boss += 1;
        } else {
          this.persistentStats.totalKills.other += 1;
        }
      }
    }
    this.persistentStats.totalExp += processedRaidStats.expGained || 0;
    this.persistentStats.averageSurvivalRate = parseFloat(
      (
        (this.persistentStats.totalSurvived / this.persistentStats.totalRaids) *
        100
      ).toFixed(2)
    );
    this.persistentStats.raidHistory.push(processedRaidStats);
    if (
      this.persistentStats.raidHistory.length >
      (this.modConfig.maxRaidHistory || 50)
    ) {
      this.persistentStats.raidHistory.shift();
    }
    this.logger?.info("Persistent stats updated.");
  }
}

module.exports = { mod: new DetailedStatsTrackerFikaFinalPatch() };
